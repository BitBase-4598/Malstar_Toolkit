export default function ActivityLog({ entries, loading }) {
  return (
    <section className="card log-card">
      <div className="summary">
        <strong>Activity log</strong>
        <span>Every step with timestamp to the second</span>
      </div>
      <div className="log-list">
        {loading && entries.length === 0 ? (
          <p className="log-empty">Loading log...</p>
        ) : entries.length === 0 ? (
          <p className="log-empty">No activity recorded yet.</p>
        ) : (
          entries.map((entry) => (
            <div key={entry.id} className="log-row">
              <time dateTime={entry.timestamp}>{entry.timestamp}</time>
              <span className="log-action">{entry.action}</span>
              {entry.detail ? <span className="log-detail">{entry.detail}</span> : null}
            </div>
          ))
        )}
      </div>
    </section>
  );
}
