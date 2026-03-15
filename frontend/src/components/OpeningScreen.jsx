const lines = [
  "Every organism occupies a position within a living system.",
  "Some stabilize.",
  "Some observe.",
  "Some intervene.",
  "This assessment will estimate where your presence creates the least disturbance.",
  "Respond quickly.",
  "Alignment is often instinctive.",
];

export default function OpeningScreen({ onNext }) {
  return (
    <div className="screen opening-screen">
      <div className="opening-content">
        <p className="opening-label">Opening</p>
        <div className="opening-lines">
          {lines.map((line, i) => (
            <p key={i} className="opening-line" style={{ animationDelay: `${i * 0.18}s` }}>
              {line}
            </p>
          ))}
        </div>
        <button className="btn btn-primary" onClick={onNext}>
          Next
        </button>
      </div>
    </div>
  );
}
