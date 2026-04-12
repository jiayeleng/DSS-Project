import { useState } from "react";

export default function NextButton({ onClick, label = "NEXT" }) {
  const [animating, setAnimating] = useState(false);

  function handleClick() {
    if (animating) return;
    setAnimating(true);
    // trigger route change partway through so transitions overlap
    setTimeout(() => onClick?.(), 500);
  }

  return (
    <button
      className={`next-btn${animating ? " next-btn--go" : ""}`}
      onClick={handleClick}
      aria-label={label}
    >
      <span className="next-btn__label" aria-hidden="true">{label}</span>
      <span className="next-btn__square" />
      <span className="next-btn__arrow" aria-hidden="true" />
    </button>
  );
}
