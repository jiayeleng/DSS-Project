export default function SplashScreen({ onStart }) {
  return (
    <div className="screen splash-screen">
      <div className="splash-image-wrapper">
        <div className="splash-image" />
        <div className="splash-overlay" />
      </div>
      <div className="splash-content">
        <button className="btn btn-primary" onClick={onStart}>
          Start
        </button>
      </div>
    </div>
  );
}
