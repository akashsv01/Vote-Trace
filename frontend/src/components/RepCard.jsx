import { ChevronIcon } from "./Icons.jsx";

function partyAbbrev(party) {
  if (!party) return "";
  const p = party.toLowerCase();
  if (p.includes("democrat")) return "D";
  if (p.includes("republican")) return "R";
  if (p.includes("independent")) return "I";
  return party.slice(0, 1).toUpperCase();
}

function partyClass(party) {
  const a = partyAbbrev(party);
  if (a === "D") return "party-d";
  if (a === "R") return "party-r";
  return "party-other";
}

export default function RepCard({ rep, expanded, onToggle, children }) {
  const initials = rep.name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0])
    .join("")
    .toUpperCase();

  return (
    <div className={`rep-card ${expanded ? "expanded" : ""}`}>
      <button
        className="rep-header"
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <div className="rep-photo-wrap">
          {rep.photo_url ? (
            <img src={rep.photo_url} alt="" className="rep-photo" />
          ) : (
            <div className="rep-photo rep-photo-placeholder">{initials}</div>
          )}
        </div>
        <div className="rep-meta">
          <div className="rep-name-row">
            <h3 className="rep-name">{rep.name}</h3>
            <span className={`party-badge ${partyClass(rep.party)}`}>
              {partyAbbrev(rep.party)}
            </span>
          </div>
          <div className="rep-title">{rep.title}</div>
        </div>
        <div className="rep-chevron">
          <ChevronIcon open={expanded} size={20} />
        </div>
      </button>
      {expanded && <div className="rep-body">{children}</div>}
    </div>
  );
}
