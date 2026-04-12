import { useState, useRef, useEffect } from "react";
import { QRCodeSVG } from "qrcode.react";

function getQrBase() {
  if (import.meta.env.VITE_QR_BASE) return import.meta.env.VITE_QR_BASE;
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  return `http://${window.location.hostname}:8000`;
}
const QR_BASE = getQrBase();
const QR_SUFFIX = import.meta.env.VITE_QR_BASE ? ".html" : "";

const NAV = [
  { id: "about",              label: "About the Role" },
  { id: "responsibilities",   label: "Responsibilities" },
  { id: "qualifications",     label: "Qualifications" },
  { id: "benefits",           label: "Benefits" },
  { id: "ecological-context", label: "Ecological Context" },
  { id: "qr-share",           label: "QR Share" },
];

export default function JobDialog({ job, onClose }) {
  const [active, setActive] = useState("about");
  const bodyRef = useRef(null);

  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function scrollTo(id) {
    setActive(id);
    const el = document.getElementById(`jd-${id}`);
    if (el && bodyRef.current) {
      const offset =
        el.getBoundingClientRect().top -
        bodyRef.current.getBoundingClientRect().top +
        bodyRef.current.scrollTop -
        24;
      bodyRef.current.scrollTo({ top: offset, behavior: "smooth" });
    }
  }

  return (
    <div className="jd-backdrop" onClick={onClose}>

      {/* Shell: nav floats left, modal sits right */}
      <div className="jd-shell" onClick={(e) => e.stopPropagation()}>

        {/* Nav column: close button on top, nav items below */}
        <div className="jd-nav-col">
          <button className="jd-close" onClick={onClose} aria-label="Close">✕</button>
          <nav className="jd-nav" aria-label="Job sections">
            {NAV.map((s) => (
              <button
                key={s.id}
                className={`jd-nav-item${active === s.id ? " jd-nav-item--active" : ""}`}
                onClick={() => scrollTo(s.id)}
              >
                {s.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Dialog box — has the offset outline frame */}
        <div className="jd-modal" role="dialog" aria-modal="true">
          <div className="jd-body" ref={bodyRef}>

            {/* Title + QR */}
            <div className="jd-header">
              <h1 className="jd-title">{job.title}</h1>
              <QRCodeSVG
                value={`${QR_BASE}/jobs/${job.id}${QR_SUFFIX}`}
                size={96}
                bgColor="transparent"
                fgColor="#ffffff"
              />
            </div>
            <div className="jd-rule" />

            {/* Meta grid */}
            <div className="jd-meta">
              {[
                ["Employment", job.employment_status],
                ["Salary",     job.salary_range],
                ["Location",   job.location],
                ["Duration",   job.duration],
              ].map(([label, value]) => (
                <div key={label} className="jd-meta-item">
                  <span className="jd-meta-label">{label}</span>
                  <span className="jd-meta-value">{value || "—"}</span>
                </div>
              ))}
            </div>

            {/* Cover image */}
            {job.cover_image && (
              <div
                className="jd-cover"
                style={{ backgroundImage: `url(${job.cover_image}), url("/mock-images/fallback.png")` }}
              />
            )}

            {/* About */}
            <section id="jd-about" className="jd-section">
              <h2 className="jd-section-heading">About the Role</h2>
              <div className="jd-rule jd-rule--sm" />
              <p className="jd-text">{job.summary || job.short_summary}</p>
            </section>

            {/* Responsibilities */}
            {job.responsibilities?.length > 0 && (
              <section id="jd-responsibilities" className="jd-section">
                <h2 className="jd-section-heading">Responsibilities</h2>
                <div className="jd-rule jd-rule--sm" />
                <ul className="jd-list">
                  {job.responsibilities.map((item, i) => <li key={i}>{item}</li>)}
                </ul>
              </section>
            )}

            {/* Qualifications */}
            {job.qualifications?.length > 0 && (
              <section id="jd-qualifications" className="jd-section">
                <h2 className="jd-section-heading">Qualifications</h2>
                <div className="jd-rule jd-rule--sm" />
                <ul className="jd-list">
                  {job.qualifications.map((item, i) => <li key={i}>{item}</li>)}
                </ul>
              </section>
            )}

            {/* Benefits */}
            {job.benefits?.length > 0 && (
              <section id="jd-benefits" className="jd-section">
                <h2 className="jd-section-heading">Benefits</h2>
                <div className="jd-rule jd-rule--sm" />
                <ul className="jd-list">
                  {job.benefits.map((item, i) => <li key={i}>{item}</li>)}
                </ul>
              </section>
            )}

            {/* Ecological Context */}
            {job.ecological_context && (
              <section id="jd-ecological-context" className="jd-section">
                <h2 className="jd-section-heading">Ecological Context</h2>
                <div className="jd-rule jd-rule--sm" />
                <p className="jd-text">{job.ecological_context}</p>
              </section>
            )}

            {/* QR Share */}
            <section id="jd-qr-share" className="jd-section">
              <h2 className="jd-section-heading">QR Share</h2>
              <div className="jd-rule jd-rule--sm" />
              <div className="jd-qr-share">
                <QRCodeSVG
                  value={`${QR_BASE}/jobs/${job.id}${QR_SUFFIX}`}
                  size={140}
                  bgColor="transparent"
                  fgColor="#ffffff"
                />
                <p className="jd-text">Scan to access full position details on your device.</p>
              </div>
            </section>

          </div>
        </div>

      </div>
    </div>
  );
}
