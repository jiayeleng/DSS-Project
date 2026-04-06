export default function SplashScreen({ onStart }) {
  return (
    <div className="screen splash-screen">
      <div className="splash-image-wrapper">
        <video
          className="splash-video"
          autoPlay
          loop
          muted
          playsInline
          aria-hidden="true"
        >
          <source src="/video/logo.mp4" type="video/mp4" />
        </video>
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
