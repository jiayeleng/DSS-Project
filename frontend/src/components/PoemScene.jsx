const stanzas = [
  [
    "Every organism occupies",
    "a position within a living system.",
  ],
  [
    "Some stabilize.",
    "Some observe.",
    "Some intervene.",
  ],
  [
    "This assessment will estimate",
    "where your presence creates",
    "the least disturbance.",
  ],
  [
    "Respond quickly.",
    "Alignment is often instinctive.",
  ],
];

export default function PoemScene() {
  return (
    <div className="poem-scene">
      <div className="poem-header">
        <span className="poem-label">Opening</span>
        <span className="poem-rule" />
      </div>

      <div className="poem-box">
        <div className="poem-body">
          {stanzas.map((stanza, si) => (
            <div key={si} className="poem-stanza">
              {stanza.map((line, li) => (
                <p
                  key={li}
                  className="poem-line opening-line"
                  style={{ animationDelay: `${(si * 4 + li) * 0.15}s` }}
                >
                  {line}
                </p>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
