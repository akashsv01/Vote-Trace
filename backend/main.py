"""FastAPI backend for 'My Rep's Voting Record, Explained'.

Three endpoints, mirroring the MVP spec:

  POST /reps              -> address -> federal reps (House + Senate)
  GET  /votes/{bioguide}  -> last 10 votes for a member (live, with fallback)
  POST /explain           -> Claude generates a plain-language vote explanation
"""

from __future__ import annotations

import asyncio
import datetime
import os
import re
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from fallback_votes import votes_for_chamber
from legislators import KNOWN_LEGISLATORS, get_legislator

load_dotenv()

GOOGLE_CIVIC_API_KEY = os.getenv("GOOGLE_CIVIC_API_KEY", "")  # legacy, unused
CONGRESS_API_KEY = os.getenv("CONGRESS_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

STATE_NAME_TO_ABBREV = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME",
    "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY", "puerto rico": "PR",
}


def state_abbrev(value: str) -> str:
    if not value:
        return ""
    v = value.strip()
    if len(v) == 2:
        return v.upper()
    return STATE_NAME_TO_ABBREV.get(v.lower(), v.upper()[:2])


def bioguide_photo_url(bioguide_id: str) -> str:
    if not bioguide_id:
        return ""
    return f"https://bioguide.congress.gov/bioguide/photo/{bioguide_id[0].upper()}/{bioguide_id}.jpg"

CURRENT_CONGRESS = 119
CURRENT_SESSION = 2

SENATE_UA = "MyRepVotingRecord/1.0 (civic education project)"
SENATE_LIST_URL = "https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_{congress}_{session}.xml"
SENATE_VOTE_URL = "https://www.senate.gov/legislative/LIS/roll_call_votes/vote{congress}{session}/vote_{congress}_{session}_{vote:05d}.xml"

http_client: Optional[httpx.AsyncClient] = None
anthropic_client: Optional[AsyncAnthropic] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, anthropic_client
    http_client = httpx.AsyncClient(timeout=15.0)
    anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
    try:
        yield
    finally:
        await http_client.aclose()


app = FastAPI(title="My Rep's Voting Record, Explained", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Models ----------


class RepsRequest(BaseModel):
    address: str


class ExplainRequest(BaseModel):
    bill_title: str
    bill_description: str
    vote_position: str
    rep_name: str
    user_context: Optional[str] = None


# ---------- /reps ----------


async def _geocode_address(address: str) -> Optional[dict]:
    """Use the U.S. Census geocoder to resolve an address to state + congressional district.
    Free, no key required. Returns {'state': 'NY', 'district': '12'} or None.
    """
    assert http_client is not None
    url = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "format": "json",
        "layers": "all",
    }
    try:
        r = await http_client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPError:
        return None

    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    match = matches[0]

    components = match.get("addressComponents", {})
    state_raw = components.get("state", "")
    state = state_abbrev(state_raw)

    geographies = match.get("geographies", {})
    district = None
    for key, entries in geographies.items():
        if "Congressional Districts" in key and entries:
            entry = entries[0]
            district = entry.get("BASENAME") or entry.get("CD119FP") or entry.get("CD118FP") or entry.get("NAME", "")
            break

    if not state:
        return None

    return {"state": state, "district": str(district) if district is not None else None}


def _district_matches(legislator_district, target_district) -> bool:
    """Tolerant district comparison. House districts can be 0/1/'00'/'At Large' etc."""
    if target_district is None:
        return False
    a = str(legislator_district or "").lstrip("0") or "0"
    b = str(target_district or "").lstrip("0") or "0"
    if a == b:
        return True
    # Some at-large states use "0" for the legislator and "98" or text for the geocoder
    if a in ("0", "1") and b in ("0", "1", "98", "at large", "at-large"):
        return True
    return False


def _serialize(legislator: dict, title: str) -> dict:
    return {
        "name": legislator.get("name") or "",
        "title": title,
        "party": (legislator.get("party") or "").replace(" Party", ""),
        "state": legislator.get("state") or "",
        "chamber": legislator.get("chamber"),
        "bioguide_id": legislator.get("bioguide_id"),
        "photo_url": bioguide_photo_url(legislator.get("bioguide_id") or ""),
    }


@app.post("/reps")
async def get_reps(req: RepsRequest):
    geo = await _geocode_address(req.address)
    if not geo:
        raise HTTPException(
            status_code=400,
            detail="Could not locate that address. Try a full street address with city and state.",
        )

    state = geo["state"]
    district = geo["district"]

    senators = [
        l for l in KNOWN_LEGISLATORS.values()
        if l["state"] == state and l["chamber"] == "senate"
    ]
    senators.sort(key=lambda l: (l.get("name") or "").split()[-1])

    house_reps = []
    for l in KNOWN_LEGISLATORS.values():
        if l["state"] != state or l["chamber"] != "house":
            continue
        if district is not None and not _district_matches(l.get("district"), district):
            continue
        house_reps.append(l)

    reps = []
    for s in senators[:2]:
        reps.append(_serialize(s, "U.S. Senator"))
    for h in house_reps[:1]:
        title = "U.S. Representative"
        d = h.get("district")
        if d not in (None, "", 0, "0"):
            title = f"U.S. Representative — {state} District {d}"
        reps.append(_serialize(h, title))

    if not reps:
        raise HTTPException(
            status_code=404,
            detail=f"No federal representatives found for {state}" + (f" district {district}" if district else "") + ".",
        )

    return {"reps": reps, "resolved": {"state": state, "district": district}}


# ---------- /votes/{bioguide_id} ----------


def _empty_to_fallback(chamber: str, reason: str):
    return {"votes": votes_for_chamber(chamber, limit=10), "source": "fallback", "reason": reason}


async def _fetch_house_vote_members(congress: int, session: int, vote_number: int):
    assert http_client is not None
    url = f"https://api.congress.gov/v3/house-vote/{congress}/{session}/{vote_number}/members"
    r = await http_client.get(url, params={"api_key": CONGRESS_API_KEY, "format": "json", "limit": 600})
    r.raise_for_status()
    return r.json()


async def _fetch_bill_summary(congress: int, bill_type: str, bill_number: str):
    """Best-effort fetch of bill title + summary. Returns (title, summary) or ('', '')."""
    assert http_client is not None
    bt = (bill_type or "").lower()
    if not (bt and bill_number):
        return "", ""
    url = f"https://api.congress.gov/v3/bill/{congress}/{bt}/{bill_number}"
    try:
        r = await http_client.get(url, params={"api_key": CONGRESS_API_KEY, "format": "json"})
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPError:
        return "", ""
    bill = data.get("bill", {}) if isinstance(data, dict) else {}
    title = bill.get("title") or ""
    summary = ""
    summaries = bill.get("summaries", {})
    if isinstance(summaries, dict):
        items = summaries.get("text") or []
        if isinstance(items, list) and items:
            summary = items[0].get("text", "")
    return title, summary


def _extract_member_position(roster_payload: dict, bioguide_id: str) -> Optional[str]:
    """Walk the various shapes the members payload may have and find our member."""
    candidates = []
    for key in ("results", "members", "houseRollCallVoteMemberVotes", "senateRollCallVoteMemberVotes"):
        v = roster_payload.get(key)
        if isinstance(v, list):
            candidates.extend(v)
        elif isinstance(v, dict):
            for sub in v.values():
                if isinstance(sub, list):
                    candidates.extend(sub)
    for wrapper in ("houseRollCallVote", "senateRollCallVote"):
        wrapped = roster_payload.get(wrapper)
        if isinstance(wrapped, dict):
            for key in ("members", "memberVotes", "results"):
                v = wrapped.get(key)
                if isinstance(v, list):
                    candidates.extend(v)

    for member in candidates:
        if not isinstance(member, dict):
            continue
        mid = (
            member.get("bioguideID")
            or member.get("bioguideId")
            or member.get("bioguide_id")
            or member.get("bioGuideId")
        )
        if mid == bioguide_id:
            position = (
                member.get("voteCast")
                or member.get("votePosition")
                or member.get("vote_cast")
                or member.get("position")
                or member.get("vote")
            )
            return position
    return None


def _normalize_position(raw: Optional[str]) -> str:
    if not raw:
        return "Not Voting"
    r = raw.strip().lower()
    if r in ("yea", "aye", "yes"):
        return "Yes"
    if r in ("nay", "no"):
        return "No"
    if r == "present":
        return "Present"
    return "Not Voting"


def _parse_senate_vote_date(raw: str) -> str:
    if not raw:
        return ""
    m = re.match(r"\s*([A-Za-z]+ \d+,\s*\d{4})", raw)
    if not m:
        return raw[:10]
    cleaned = re.sub(r"\s+", " ", m.group(1))
    try:
        dt = datetime.datetime.strptime(cleaned, "%B %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return raw[:10]


def _senate_vote_position(raw: str) -> str:
    if not raw:
        return "Not Voting"
    r = raw.strip().lower()
    if r in ("yea", "aye", "yes"):
        return "Yes"
    if r in ("nay", "no"):
        return "No"
    if r == "present":
        return "Present"
    return "Not Voting"


def _last_name(full_name: str) -> str:
    """Extract a comparable last name from a legislator's full name."""
    cleaned = re.sub(r",.*$", "", full_name or "").strip()
    parts = cleaned.split()
    if not parts:
        return ""
    suffixes = {"jr.", "jr", "sr.", "sr", "iii", "ii", "iv"}
    while len(parts) > 1 and parts[-1].lower() in suffixes:
        parts.pop()
    return parts[-1].lower()


async def _fetch_senate_votes(bioguide_id: str, congress: int, session: int, limit: int = 10):
    assert http_client is not None
    legislator = get_legislator(bioguide_id)
    if not legislator:
        return None
    senator_last = _last_name(legislator.get("name", ""))
    senator_state = legislator.get("state", "")

    list_url = SENATE_LIST_URL.format(congress=congress, session=session)
    try:
        r = await http_client.get(list_url, headers={"User-Agent": SENATE_UA})
        r.raise_for_status()
        list_root = ET.fromstring(r.content)
    except (httpx.HTTPError, ET.ParseError) as e:
        return None

    votes_container = list_root.find("votes")
    if votes_container is None:
        return None

    items = list(votes_container)[:limit]

    async def fetch_one(item):
        vote_num_str = item.findtext("vote_number") or ""
        try:
            vote_num = int(vote_num_str)
        except ValueError:
            return None
        url = SENATE_VOTE_URL.format(congress=congress, session=session, vote=vote_num)
        try:
            rd = await http_client.get(url, headers={"User-Agent": SENATE_UA})
            rd.raise_for_status()
            detail = ET.fromstring(rd.content)
        except (httpx.HTTPError, ET.ParseError):
            return None

        position = "Not Voting"
        members = detail.find("members")
        if members is not None:
            for m in members:
                last = (m.findtext("last_name") or "").lower()
                state = m.findtext("state") or ""
                if last == senator_last and state == senator_state:
                    position = _senate_vote_position(m.findtext("vote_cast") or "")
                    break

        question = (detail.findtext("vote_question_text") or "").strip()
        document_text = (detail.findtext("vote_document_text") or "").strip()
        result_text = (detail.findtext("vote_result_text") or detail.findtext("vote_result") or "").strip()

        doc_node = detail.find("document")
        doc_short = (doc_node.findtext("document_short_title") if doc_node is not None else "") or ""
        doc_title = (doc_node.findtext("document_title") if doc_node is not None else "") or ""

        amendment_node = detail.find("amendment")
        amend_purpose = (
            amendment_node.findtext("amendment_purpose") if amendment_node is not None else ""
        ) or ""

        title_pieces = []
        if doc_short:
            title_pieces.append(doc_short)
        elif document_text:
            title_pieces.append(document_text[:140])
        if question and not title_pieces:
            title_pieces.append(question)
        title = " — ".join(p for p in title_pieces if p) or "Senate roll-call vote"

        desc_pieces = []
        if document_text:
            desc_pieces.append(document_text)
        if doc_title and doc_title != doc_short:
            desc_pieces.append(doc_title)
        if amend_purpose:
            desc_pieces.append(f"Amendment purpose: {amend_purpose}")
        if question:
            desc_pieces.append(f"Question before the Senate: {question}")
        if result_text:
            desc_pieces.append(f"Result: {result_text}")
        description = " ".join(desc_pieces) or "No additional details available."

        return {
            "bill_id": f"senate-{congress}-{session}-{vote_num}",
            "bill_title": title,
            "bill_description": description,
            "date": _parse_senate_vote_date(detail.findtext("vote_date") or ""),
            "vote_position": position,
        }

    results = await asyncio.gather(*(fetch_one(i) for i in items))
    return [v for v in results if v is not None]


@app.get("/votes/{bioguide_id}")
async def get_votes(bioguide_id: str):
    legislator = get_legislator(bioguide_id)
    if not legislator:
        return _empty_to_fallback("house", reason=f"Unknown bioguide_id {bioguide_id}")

    chamber = legislator["chamber"]

    if chamber == "senate":
        votes = await _fetch_senate_votes(bioguide_id, CURRENT_CONGRESS, CURRENT_SESSION, limit=10)
        if votes:
            return {"votes": votes, "source": "live"}
        # fall back to previous session if current is empty
        votes = await _fetch_senate_votes(bioguide_id, CURRENT_CONGRESS, CURRENT_SESSION - 1, limit=10)
        if votes:
            return {"votes": votes, "source": "live"}
        return _empty_to_fallback("senate", reason="Senate.gov XML feed returned no votes")

    if not CONGRESS_API_KEY:
        return _empty_to_fallback(chamber, reason="CONGRESS_API_KEY not set")

    list_url = "https://api.congress.gov/v3/house-vote"

    try:
        r = await http_client.get(list_url, params={"api_key": CONGRESS_API_KEY, "limit": 20, "format": "json"})
        r.raise_for_status()
        list_data = r.json()
    except httpx.HTTPError as e:
        return _empty_to_fallback(chamber, reason=f"Congress API list error: {e}")

    items = list_data.get("houseRollCallVotes") or []
    if not items:
        return _empty_to_fallback(chamber, reason="No recent votes returned")

    async def fetch_one(item):
        congress = item.get("congress")
        session = item.get("sessionNumber")
        vote_number = item.get("rollCallNumber")
        if not (congress and session and vote_number):
            return None
        try:
            roster = await _fetch_house_vote_members(int(congress), int(session), int(vote_number))
        except httpx.HTTPError:
            return None
        position = _normalize_position(_extract_member_position(roster, bioguide_id))

        leg_type = item.get("legislationType") or ""
        leg_number = item.get("legislationNumber") or ""
        bill_label = f"{leg_type} {leg_number}".strip() or f"Roll Call {vote_number}"

        bill_title, bill_summary = "", ""
        if leg_type and leg_number:
            bill_title, bill_summary = await _fetch_bill_summary(int(congress), leg_type, str(leg_number))

        title = f"{bill_label} — {bill_title}" if bill_title else bill_label
        description = bill_summary or item.get("voteType") or "No bill summary available."
        date = (item.get("startDate") or "")[:10]

        return {
            "bill_id": f"house-{congress}-{session}-{vote_number}",
            "bill_title": title,
            "bill_description": description,
            "date": date,
            "vote_position": position,
        }

    results = await asyncio.gather(*(fetch_one(item) for item in items[:10]))
    votes = [v for v in results if v is not None]

    if not votes:
        return _empty_to_fallback(chamber, reason="All vote-detail fetches failed")

    return {"votes": votes, "source": "live"}


# ---------- /explain ----------


SYSTEM_PROMPT = (
    "You are a nonpartisan civic education tool. "
    "Explain legislation in plain language so an average American can understand what "
    "the bill would actually do in concrete terms. Never editorialize. Never imply a "
    "vote was good or bad. Be factual and neutral. Avoid loaded words. Do not mention "
    "the political party of the representative. "
    "Output rules: "
    "1) Always start with a section called WHAT IT DOES with 2-3 plain-language sentences "
    "describing the bill's actual effect. "
    "2) If, AND ONLY IF, the user provides personal context, also include a second section "
    "called PERSONAL IMPACT with 1-2 sentences describing how the bill might directly "
    "affect someone with that context. Be specific to their situation, but only state "
    "effects that are actually plausible from the bill text. If the bill has no realistic "
    "personal effect on this person, say so plainly in PERSONAL IMPACT. "
    "Format each section as: 'WHAT IT DOES: <text>' on one line, then 'PERSONAL IMPACT: "
    "<text>' on the next line. Do not add extra commentary or headings."
)


@app.post("/explain")
async def explain_vote(req: ExplainRequest):
    if anthropic_client is None:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    user_context = (req.user_context or "").strip()

    user_prompt_lines = [
        f"Bill: {req.bill_title}",
        f"Official description: {req.bill_description}",
        f"{req.rep_name} voted: {req.vote_position}",
    ]
    if user_context:
        user_prompt_lines.append("")
        user_prompt_lines.append(f"User personal context: {user_context}")
        user_prompt_lines.append(
            "Produce both WHAT IT DOES and PERSONAL IMPACT sections."
        )
    else:
        user_prompt_lines.append("")
        user_prompt_lines.append(
            "No personal context provided. Produce WHAT IT DOES only."
        )

    try:
        msg = await anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": "\n".join(user_prompt_lines)}],
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Anthropic error: {e}")

    raw = "".join(block.text for block in msg.content if getattr(block, "type", None) == "text").strip()

    # Split sections. Be tolerant of variations.
    what_it_does = raw
    personal_impact = ""
    upper = raw.upper()
    pi_idx = upper.find("PERSONAL IMPACT:")
    if pi_idx != -1:
        what_part = raw[:pi_idx].strip()
        personal_part = raw[pi_idx + len("PERSONAL IMPACT:"):].strip()
        # Strip leading "WHAT IT DOES:" if present
        wit_upper = what_part.upper()
        wit_idx = wit_upper.find("WHAT IT DOES:")
        if wit_idx != -1:
            what_part = what_part[wit_idx + len("WHAT IT DOES:"):].strip()
        what_it_does = what_part
        personal_impact = personal_part
    else:
        wit_upper = upper.find("WHAT IT DOES:")
        if wit_upper != -1:
            what_it_does = raw[wit_upper + len("WHAT IT DOES:"):].strip()

    return {
        "explanation": what_it_does,
        "personal_impact": personal_impact,
    }


@app.get("/health")
async def health():
    return {
        "ok": True,
        "civic_key_set": bool(GOOGLE_CIVIC_API_KEY),
        "congress_key_set": bool(CONGRESS_API_KEY),
        "anthropic_key_set": bool(ANTHROPIC_API_KEY),
    }
