export default function LoadingScreen() {
  return (
    <div className="screen loading-screen">
      <div className="loading-content">
        <div className="loading-dots">
          <span /><span /><span />
        </div>
        <p className="loading-text">Evaluating ecological compatibility…</p>
      </div>
    </div>
  );
}
