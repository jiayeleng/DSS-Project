export default function RestartButton({ onClick }) {
  return (
    <button className="restart-btn" onClick={onClick} aria-label="Restart assessment">
      <span className="restart-btn__arrow" aria-hidden="true" />
      <span className="restart-btn__line" />
      <span className="restart-btn__label">Restart</span>
      <span className="restart-btn__bracket" aria-hidden="true" />
    </button>
  );
}
