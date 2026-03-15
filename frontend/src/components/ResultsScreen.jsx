import { QRCodeSVG } from 'qrcode.react';

// Build the QR base URL at runtime so it uses the real network IP.
// If VITE_API_URL is explicitly set, honour it.
// Otherwise derive from the current hostname (works when accessed via iPad on LAN).
function getQrBase() {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  const { hostname } = window.location;
  return `http://${hostname}:8000`;
}
const QR_BASE = getQrBase();

// Vary vertical crop of the placeholder image per card
const BG_POSITIONS = ['20%', '45%', '65%', '30%', '55%', '40%', '25%'];

export default function ResultsScreen({ jobs, onRestart }) {
  return (
    <div className="screen results-screen">
      <div className="results-content-wide">
        <p className="results-label">Ecological Roles</p>

        {jobs && jobs.length > 0 ? (
          <div className="jobs-grid">
            {jobs.map((job, i) => (
              <div key={job.id} className="job-card-v2">

                {/* Placeholder image */}
                <div
                  className="job-card-image"
                  style={{ backgroundPositionY: BG_POSITIONS[i % BG_POSITIONS.length] }}
                />

                {/* Short summary */}
                <div className="job-card-body">
                  <p className="job-card-title">{job.title}</p>
                  <p className="job-card-summary">
                    {job.short_summary || job.summary?.slice(0, 180)}
                  </p>
                </div>

                {/* QR code */}
                <div className="job-card-footer">
                  <QRCodeSVG
                    value={`${QR_BASE}/jobs/${job.id}`}
                    size={88}
                    bgColor="transparent"
                    fgColor="#c8cfc4"
                  />
                </div>

              </div>
            ))}
          </div>
        ) : (
          <p className="no-results">No roles matched your profile. Try again.</p>
        )}

        <button className="btn btn-secondary" onClick={onRestart}>
          Take Assessment Again
        </button>
      </div>
    </div>
  );
}
