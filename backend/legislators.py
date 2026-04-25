"""Legislator lookup. Maps (name, state, chamber) returned by Google Civic to the
bioguide_id used by api.congress.gov.

On first run the module downloads the public legislator dataset from
theunitedstates.io and caches it on disk. After that it works fully offline.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Optional

DATA_URLS = [
    "https://unitedstates.github.io/congress-legislators/legislators-current.json",
    "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/legislators-current.json",
    "https://theunitedstates.io/congress-legislators/legislators-current.json",
]
DATA_FILE = Path(__file__).parent / "legislators_current.json"

REQUEST_HEADERS = {
    "User-Agent": "MyRepVotingRecord/1.0 (hackathon project; civic education)",
    "Accept": "application/json",
}


def _normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _load_raw() -> list:
    if DATA_FILE.exists():
        try:
            with DATA_FILE.open() as f:
                return json.load(f)
        except Exception:
            pass
    last_error: Optional[Exception] = None
    for url in DATA_URLS:
        try:
            req = urllib.request.Request(url, headers=REQUEST_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode("utf-8"))
            with DATA_FILE.open("w") as f:
                json.dump(data, f)
            print(f"[legislators] Loaded dataset from {url}")
            return data
        except Exception as e:
            last_error = e
            continue
    print(f"[legislators] Could not download dataset from any source: {last_error}")
    return []


def _build_index(raw: list) -> dict:
    """Build an index keyed by (normalized_name, state, chamber)."""
    index: dict[tuple[str, str, str], dict] = {}
    for entry in raw:
        terms = entry.get("terms", [])
        if not terms:
            continue
        current = terms[-1]
        chamber = "senate" if current.get("type") == "sen" else "house"
        state = (current.get("state") or "").upper()
        bioguide_id = entry.get("id", {}).get("bioguide")
        if not bioguide_id:
            continue
        names = entry.get("name", {})
        first = names.get("first", "")
        last = names.get("last", "")
        nickname = names.get("nickname")
        official_full = names.get("official_full", f"{first} {last}")

        candidates = {
            f"{first} {last}",
            official_full,
        }
        if nickname:
            candidates.add(f"{nickname} {last}")

        record = {
            "bioguide_id": bioguide_id,
            "name": official_full,
            "state": state,
            "chamber": chamber,
            "district": current.get("district"),
            "party": current.get("party"),
        }

        for cand in candidates:
            key = (_normalize(cand), state, chamber)
            index[key] = record
        # also index by last name only as a fallback
        index[(_normalize(last), state, chamber)] = record
    return index


_RAW = _load_raw()
_INDEX = _build_index(_RAW)
KNOWN_LEGISLATORS = {r["bioguide_id"]: r for r in _INDEX.values()}


def find_bioguide_id(name: str, state: str, chamber: str) -> Optional[str]:
    state = (state or "").upper()
    n = _normalize(name)
    record = _INDEX.get((n, state, chamber))
    if record:
        return record["bioguide_id"]
    # try last name only
    parts = n.split()
    if parts:
        record = _INDEX.get((parts[-1], state, chamber))
        if record:
            return record["bioguide_id"]
    return None


def get_legislator(bioguide_id: str) -> Optional[dict]:
    return KNOWN_LEGISLATORS.get(bioguide_id)
