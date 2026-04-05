/**
 * @param {Object} answers - User's answers to the 5 questions
 * @param {string} answers.lifeSystems        - "plants" | "animals" | "environmental systems"
 * @param {string} answers.habitatDomain      - "land" | "water" | "air"
 * @param {string} answers.circadianPhase     - "day" | "night"
 * @param {string} answers.operationalSetting - "indoor" | "field work"
 * @param {string} answers.interactionMode    - "observe" | "help" | "touch"
 * @returns {Promise<Array>} Array of job objects from the database
 */

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function fetchJobs(answers) {
  const response = await fetch(`${API_BASE}/api/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(answers),
  });

  if (!response.ok) {
    throw new Error(`API error ${response.status}`);
  }

  const jobs = await response.json();
  return jobs.map((job, i) => ({ ...job, id: job.id ?? i + 1 }));
}
