import { QRCodeSVG } from "qrcode.react";

// Build the QR base URL at runtime.
// VITE_QR_BASE  — set this to a public static-hosting URL so QR codes work
//                 without LAN access (e.g. https://your-site.netlify.app).
//                 Run `python export_static.py` first to generate the files.
// VITE_API_URL  — fallback: used when the page is served via a public API host.
// Otherwise     — derive from the current hostname (LAN / local-only mode).
function getQrBase() {
  if (import.meta.env.VITE_QR_BASE) return import.meta.env.VITE_QR_BASE;
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  const { hostname } = window.location;
  return `http://${hostname}:8000`;
}
const QR_BASE = getQrBase();
// Static hosting uses  /jobs/<id>.html;  the FastAPI server uses  /jobs/<id>
const QR_SUFFIX = import.meta.env.VITE_QR_BASE ? ".html" : "";

// Vary vertical crop of the placeholder image per card
const BG_POSITIONS = ["20%", "45%", "65%", "30%", "55%", "40%", "25%"];

export default function ResultsScreen({ jobs, onRestart, onRefresh }) {
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
                  style={{
                    backgroundImage: `url(${job.cover_image}), url("/mock-images/fallback.png")`,
                    backgroundPosition: `center ${BG_POSITIONS[i % BG_POSITIONS.length]}`,
                    backgroundSize: "cover",
                    backgroundRepeat: "no-repeat",
                  }}
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
                    value={`${QR_BASE}/jobs/${job.id}${QR_SUFFIX}`}
                    size={88}
                    bgColor="transparent"
                    fgColor="#c8cfc4"
                  />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="no-results">
            No roles matched your profile. Try again.
          </p>
        )}

        <div className="results-actions">
          <button className="btn btn-secondary" onClick={onRefresh}>
            New Batch
          </button>
          <button className="btn btn-secondary" onClick={onRestart}>
            Take Assessment Again
          </button>
        </div>
      </div>
    </div>
  );
}
