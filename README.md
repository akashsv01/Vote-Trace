# My Rep's Voting Record, Explained

Enter your address, see your federal representatives and their recent votes explained in plain English. Nonpartisan.

## Stack

- **Frontend:** React + Vite (port 5173)
- **Backend:** FastAPI + httpx (port 8000)
- **APIs:** Google Civic Information, api.congress.gov, Anthropic (Claude)

## Setup

You need three API keys:

| Key                    | Where to get it                                                                  | Cost          |
| ---------------------- | -------------------------------------------------------------------------------- | ------------- |
| `GOOGLE_CIVIC_API_KEY` | https://console.cloud.google.com → enable Civic Information API → create API key | Free          |
| `CONGRESS_API_KEY`     | https://api.congress.gov/sign-up/ → fill the form                                | Free, instant |
| `ANTHROPIC_API_KEY`    | https://console.anthropic.com → API keys                                         | Pay-as-you-go |

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env` with:

```
GOOGLE_CIVIC_API_KEY=your_key_here
CONGRESS_API_KEY=your_key_here
ANTHROPIC_API_KEY=sk-ant-your_key_here
```

Run it:

```bash
uvicorn main:app --reload --port 8000
```

First run will download the public legislators dataset (~700 KB) from theunitedstates.io and cache it locally.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## How it works

1. User enters an address. Frontend calls `/api/reps`.
2. Backend hits Google Civic API, gets federal reps, looks up their `bioguide_id` from the local legislator dataset.
3. User clicks a rep. Frontend calls `/api/votes/{bioguide_id}`.
4. Backend hits api.congress.gov: lists recent chamber votes, then in parallel fetches each vote's roster to find that member's position. Falls back to a hardcoded set of real recent votes if the live calls fail.
5. User clicks "Explain in plain language". Frontend calls `/api/explain`.
6. Backend asks Claude (Haiku 4.5) for a 2-3 sentence neutral explanation, with the system prompt cached for cost savings on subsequent calls.

## Demo path

Open http://localhost:5173, paste a real address (e.g. `1600 Pennsylvania Ave NW, Washington, DC` or your hackathon venue's address), click a senator, expand a vote, and watch Claude generate a neutral explanation live.

## What's intentionally cut

- State and local reps (federal only)
- Caching of vote data (calls api.congress.gov fresh each time)
- Auth, accounts, saved reps
- Mobile polish beyond a basic responsive layout

## Notes

- The api.congress.gov roll-call vote endpoints are relatively new and the response shapes vary slightly. The backend is defensive: any failure falls through to a curated set of real recent votes so the demo never hard-breaks.
- The system prompt for explanations is cached on Anthropic's side using `cache_control: ephemeral`. Repeated explanations during a demo are cheaper and faster.
