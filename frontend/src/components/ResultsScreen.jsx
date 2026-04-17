import { useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import RestartButton from "./RestartButton";
import JobDialog from "./JobDialog";
import SceneBackground from "./SceneBackground";
import HomeButton from "./HomeButton";

const OVERLAYS = Array.from({ length: 35 }, (_, i) => {
  const n = String(i + 1).padStart(2, "0");
  return `url("/assets/path-overlay-${n}.png")`;
});

const DOT_OVERLAYS = [1, 2, 3].map(
  (n) => `url("/assets/dot-pattern-0${n}.gif")`,
);

function getQrBase() {
  if (import.meta.env.VITE_QR_BASE) return import.meta.env.VITE_QR_BASE;
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  const { hostname } = window.location;
  return `http://${hostname}:8000`;
}
const QR_BASE = getQrBase();
const QR_SUFFIX = import.meta.env.VITE_QR_BASE ? ".html" : "";

// Vary vertical crop of the placeholder image per card
const BG_POSITIONS = ["20%", "45%", "65%", "30%", "55%", "40%", "25%"];
export default function ResultsScreen({
  jobs,
  onRestart,
  onHome,
  onNextBatch,
  onPreviousBatch,
  batchIndex,
  totalBatches,
}) {
  const hasPrevious = batchIndex > 0;
  const hasNext = batchIndex < totalBatches - 1;
  const [selectedJob, setSelectedJob] = useState(null);

  return (
    <div className="screen results-screen">
      <SceneBackground />

      {/* HUD corners */}
      <HomeButton onClick={onHome} />
      <div className="q-hud q-hud--tr">
        <span className="q-hud-label">DSS</span>
        <span className="q-hud-dot" />
      </div>

      {/* Main content */}
      <div className="results-inner">
        <h1 className="results-heading">Access Assigned DDS Position</h1>

        {jobs && jobs.length > 0 ? (
          <>
            <div className="results-scroll">
              {jobs.map((job) => (
                <div
                  key={job.id}
                  className="job-card"
                  onClick={() => setSelectedJob(job)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && setSelectedJob(job)}
                >
                  <div className="job-card-img-wrap">
                    <div
                      className="job-card-img"
                      style={{
                        backgroundImage: `url(/images/${job.id}.png), url("/mock-images/fallback.png")`,
                        "--overlay":
                          OVERLAYS[Math.floor(Math.random() * OVERLAYS.length)],
                        "--dot-overlay":
                          DOT_OVERLAYS[
                            Math.floor(Math.random() * DOT_OVERLAYS.length)
                          ],
                      }}
                    />
                  </div>

                  <div className="job-card-info">
                    <span className="job-card-type">
                      {job.employment_status || "Full-Time"}
                    </span>
                    <h2 className="job-card-title">{job.title}</h2>
                    <p className="job-card-summary">
                      {job.short_summary || job.summary?.slice(0, 160)}
                    </p>
                    <div className="job-card-meta">
                      {job.salary_range && (
                        <span className="job-card-salary">
                          {job.salary_range}
                        </span>
                      )}
                      {job.location && (
                        <span className="job-card-location">
                          {job.location}
                        </span>
                      )}
                    </div>
                    <div className="job-card-footer">
                      <span className="job-card-link">View Details →</span>
                      <QRCodeSVG
                        value={`${QR_BASE}/jobs/${job.id}${QR_SUFFIX}`}
                        size={64}
                        bgColor="transparent"
                        fgColor="rgba(255,255,255,0.35)"
                      />
                    </div>
                  </div>

                  <span className="job-card-dot job-card-dot--tl" />
                  <span className="job-card-dot job-card-dot--bl" />
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="results-empty">No roles matched your profile.</p>
        )}
      </div>

      {/* Restart — bottom right */}
      <div className="screen-next">
        {/* <button
            className="btn btn-secondary"
            onClick={onPreviousBatch}
            disabled={!hasPrevious}
          >
            Previous Batch
          </button>
          <button
            className="btn btn-secondary"
            onClick={onNextBatch}
            disabled={!hasNext}
          >
            Next Batch
          </button> */}
        <RestartButton onClick={onRestart} />
      </div>

      {/* Job detail dialog */}
      {selectedJob && (
        <JobDialog job={selectedJob} onClose={() => setSelectedJob(null)} />
      )}
    </div>
  );
}
