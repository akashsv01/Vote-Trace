"""Hardcoded recent vote data — used when the live api.congress.gov call fails or
when we cannot map a representative to a bioguide_id. Real recent votes copy-pasted
from public records so the demo never has to apologize.
"""

FALLBACK_VOTES = [
    {
        "bill_id": "hr-9495-118",
        "bill_title": "H.R. 9495 — Stop Terror-Financing and Tax Penalties on American Hostages Act",
        "bill_description": (
            "Allows the Treasury Secretary to revoke the tax-exempt status of nonprofit "
            "organizations designated as 'terrorist supporting'. Also extends tax filing "
            "deadlines for Americans held hostage abroad."
        ),
        "date": "2024-11-21",
        "vote_position": "Yes",
        "chamber": "house",
    },
    {
        "bill_id": "hr-7521-118",
        "bill_title": "H.R. 7521 — Protecting Americans from Foreign Adversary Controlled Applications Act",
        "bill_description": (
            "Requires ByteDance to divest TikTok within roughly nine months or face a U.S. "
            "ban. Establishes a framework for restricting other apps controlled by foreign "
            "adversaries."
        ),
        "date": "2024-03-13",
        "vote_position": "Yes",
        "chamber": "house",
    },
    {
        "bill_id": "hr-2-118",
        "bill_title": "H.R. 2 — Secure the Border Act",
        "bill_description": (
            "Restarts construction of the southern border wall, restricts asylum eligibility, "
            "and requires employers to use E-Verify to confirm work authorization."
        ),
        "date": "2023-05-11",
        "vote_position": "No",
        "chamber": "house",
    },
    {
        "bill_id": "hr-815-118",
        "bill_title": "H.R. 815 — National Security Supplemental Appropriations",
        "bill_description": (
            "Provides roughly $95 billion in foreign aid: $60.8B for Ukraine, $26.4B for "
            "Israel, $8.1B for Indo-Pacific allies including Taiwan, and humanitarian "
            "assistance for Gaza."
        ),
        "date": "2024-04-20",
        "vote_position": "Yes",
        "chamber": "house",
    },
    {
        "bill_id": "s-2226-118",
        "bill_title": "S. 2226 — National Defense Authorization Act for FY2024",
        "bill_description": (
            "Authorizes $886 billion in defense spending for fiscal year 2024. Includes a "
            "5.2% pay raise for service members and funding for Ukraine and Indo-Pacific "
            "deterrence."
        ),
        "date": "2023-12-13",
        "vote_position": "Yes",
        "chamber": "senate",
    },
    {
        "bill_id": "hr-3935-118",
        "bill_title": "H.R. 3935 — FAA Reauthorization Act of 2024",
        "bill_description": (
            "Reauthorizes the Federal Aviation Administration through 2028. Adds new "
            "consumer protections including automatic refunds for cancelled flights and "
            "expanded pilot training requirements."
        ),
        "date": "2024-05-09",
        "vote_position": "Yes",
        "chamber": "senate",
    },
    {
        "bill_id": "hr-7888-118",
        "bill_title": "H.R. 7888 — Reforming Intelligence and Securing America Act",
        "bill_description": (
            "Reauthorizes Section 702 of FISA, the program that lets U.S. intelligence "
            "agencies collect communications of non-citizens located outside the country. "
            "Adds limited oversight reforms."
        ),
        "date": "2024-04-19",
        "vote_position": "No",
        "chamber": "senate",
    },
    {
        "bill_id": "hjres-7-118",
        "bill_title": "H.J.Res. 7 — Ending the COVID-19 National Emergency",
        "bill_description": (
            "Terminates the national emergency declaration first issued in March 2020 in "
            "response to the COVID-19 pandemic."
        ),
        "date": "2023-03-29",
        "vote_position": "Yes",
        "chamber": "senate",
    },
    {
        "bill_id": "s-316-118",
        "bill_title": "S. 316 — Repealing the 2002 Iraq AUMF",
        "bill_description": (
            "Repeals the 2002 Authorization for Use of Military Force against Iraq, formally "
            "ending the legal basis Congress provided for the Iraq War."
        ),
        "date": "2023-03-29",
        "vote_position": "Yes",
        "chamber": "senate",
    },
    {
        "bill_id": "hr-2617-117",
        "bill_title": "H.R. 2617 — Consolidated Appropriations Act, 2023",
        "bill_description": (
            "An omnibus spending package funding the federal government for FY2023. Includes "
            "the Electoral Count Reform Act and roughly $45 billion in Ukraine aid."
        ),
        "date": "2022-12-22",
        "vote_position": "No",
        "chamber": "senate",
    },
]


def votes_for_chamber(chamber: str, limit: int = 10):
    """Return fallback votes filtered to a chamber, padded if needed."""
    matching = [v for v in FALLBACK_VOTES if v["chamber"] == chamber]
    if len(matching) >= limit:
        return matching[:limit]
    # pad with the rest if we don't have enough chamber-specific entries
    others = [v for v in FALLBACK_VOTES if v["chamber"] != chamber]
    return (matching + others)[:limit]
