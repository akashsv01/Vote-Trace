import VoteItem from "./VoteItem.jsx";

export default function VoteList({ votes, source, repName, loading, error }) {
  if (loading) {
    return <div className="vote-list-state">Loading recent votes...</div>;
  }
  if (error) {
    return <div className="vote-list-state vote-list-error">{error}</div>;
  }
  if (!votes || votes.length === 0) {
    return <div className="vote-list-state">No recent votes available.</div>;
  }

  return (
    <div>
      {source === "fallback" && (
        <div className="source-note">
          Showing recent example votes. Live data temporarily unavailable.
        </div>
      )}
      <ul className="vote-list">
        {votes.map((v) => (
          <VoteItem key={v.bill_id} vote={v} repName={repName} />
        ))}
      </ul>
    </div>
  );
}
