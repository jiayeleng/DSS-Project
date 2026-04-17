export default function HomeButton({ onClick }) {
  return (
    <button className="q-hud q-hud--tl home-btn" onClick={onClick} aria-label="Go to home">
      <svg width="36" height="36" viewBox="0 0 36 36" fill="none" stroke="currentColor" strokeWidth="1.2">
        <circle cx="18" cy="18" r="12" />
        <line x1="18" y1="0" x2="18" y2="36" />
        <line x1="0" y1="18" x2="36" y2="18" />
        <ellipse cx="18" cy="18" rx="5.5" ry="12" />
      </svg>
    </button>
  );
}
