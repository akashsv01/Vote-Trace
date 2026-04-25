import { useState } from "react";
import AddressInput from "./components/AddressInput.jsx";
import RepCard from "./components/RepCard.jsx";
import VoteList from "./components/VoteList.jsx";

export default function App() {
  const [reps, setReps] = useState(null);
  const [loadingReps, setLoadingReps] = useState(false);
  const [repsError, setRepsError] = useState("");

  const [expandedBioguide, setExpandedBioguide] = useState(null);
  const [votesByBioguide, setVotesByBioguide] = useState({});

  async function handleAddressSubmit(address) {
    setLoadingReps(true);
    setRepsError("");
    setReps(null);
    setExpandedBioguide(null);
    setVotesByBioguide({});
    try {
      const res = await fetch("/api/reps", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ address }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${res.status})`);
      }
      const data = await res.json();
      setReps(data.reps || []);
    } catch (e) {
      setRepsError(e.message || "Could not look up representatives.");
    } finally {
      setLoadingReps(false);
    }
  }

  async function handleToggleRep(rep) {
    const id = rep.bioguide_id || rep.name;
    if (expandedBioguide === id) {
      setExpandedBioguide(null);
      return;
    }
    setExpandedBioguide(id);

    if (votesByBioguide[id]) return;

    setVotesByBioguide((prev) => ({
      ...prev,
      [id]: { loading: true, votes: [], source: "", error: "" },
    }));

    try {
      if (!rep.bioguide_id) {
        setVotesByBioguide((prev) => ({
          ...prev,
          [id]: {
            loading: false,
            votes: [],
            source: "",
            error: "Could not match this representative to a voting record.",
          },
        }));
        return;
      }
      const res = await fetch(`/api/votes/${rep.bioguide_id}`);
      if (!res.ok) throw new Error(`Request failed (${res.status})`);
      const data = await res.json();
      setVotesByBioguide((prev) => ({
        ...prev,
        [id]: {
          loading: false,
          votes: data.votes || [],
          source: data.source || "",
          error: "",
        },
      }));
    } catch (e) {
      setVotesByBioguide((prev) => ({
        ...prev,
        [id]: {
          loading: false,
          votes: [],
          source: "",
          error: e.message || "Failed to load votes.",
        },
      }));
    }
  }

  // Senators first, then House
  const sortedReps = reps
    ? [...reps].sort((a, b) => {
        if (a.chamber === b.chamber) return a.name.localeCompare(b.name);
        return a.chamber === "senate" ? -1 : 1;
      })
    : null;

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">My Rep's Voting Record, Explained</h1>
        <p className="app-tagline">
          Your federal representatives. Their recent votes. Translated into
          plain English. Nonpartisan.
        </p>
      </header>

      <main className="app-main">
        <AddressInput onSubmit={handleAddressSubmit} disabled={loadingReps} />

        {repsError && <div className="error-banner">{repsError}</div>}

        {sortedReps && sortedReps.length === 0 && !loadingReps && (
          <div className="empty-state">
            No federal representatives found for that address.
          </div>
        )}

        {sortedReps && sortedReps.length > 0 && (
          <section className="reps-section">
            <h2 className="section-heading">Your federal representatives</h2>
            <div className="reps-grid">
              {sortedReps.map((rep) => {
                const id = rep.bioguide_id || rep.name;
                const isExpanded = expandedBioguide === id;
                const voteState = votesByBioguide[id] || {};
                return (
                  <RepCard
                    key={id}
                    rep={rep}
                    expanded={isExpanded}
                    onToggle={() => handleToggleRep(rep)}
                  >
                    <VoteList
                      votes={voteState.votes}
                      source={voteState.source}
                      repName={rep.name}
                      loading={voteState.loading}
                      error={voteState.error}
                    />
                  </RepCard>
                );
              })}
            </div>
          </section>
        )}
      </main>

      <footer className="app-footer">
        Data: Google Civic Information API + api.congress.gov. Explanations by
        Claude.
      </footer>
    </div>
  );
}
