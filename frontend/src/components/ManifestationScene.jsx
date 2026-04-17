import { useEffect, useState } from "react";

const lines = [
  "The Department of Species Services (DSS) is an AI-managed ecological commons that assigns human roles to support planetary systems.",
  "By monitoring environmental conditions and reallocating labor where needed, DSS redefines work as ecological function, coordinating humans, machines, and non-human life.",
];

function useClock() {
  const [time, setTime] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  const days = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
  const day = days[time.getDay()];
  const hh = String(time.getHours()).padStart(2, "0");
  const mm = String(time.getMinutes()).padStart(2, "0");
  const ampm = time.getHours() >= 12 ? "PM" : "AM";
  return `${day} ${hh}:${mm} ${ampm}`;
}

export default function ManifestationScene() {
  const clock = useClock();

  return (
    <div className="manifest-scene">
      {/* Seal */}
      <img
        src="/assets/logo.svg"
        alt="Department of Species Services seal"
        className="manifest-seal"
      />

      {/* Body text */}
      <div className="manifest-text">
        {lines.map((line, i) => (
          <p
            key={i}
            className="manifest-line opening-line"
            style={{ animationDelay: `${i * 0.35}s` }}
          >
            {line}
          </p>
        ))}
      </div>

      {/* Bottom-left status bar */}
      <div className="manifest-status">
        <span className="manifest-status-time">{clock}</span>
        <span className="manifest-status-version">V1.01 / 26</span>
        <span className="manifest-status-bar" />
      </div>
    </div>
  );
}
