/**
 * @param {Object} answers - User's answers to the 5 questions
 * @param {string} answers.lifeSystems        - "plants" | "animals" | "environmental systems"
 * @param {string} answers.habitatDomain      - "land" | "water" | "air"
 * @param {string} answers.circadianPhase     - "day" | "night"
 * @param {string} answers.operationalSetting - "indoor" | "field work"
 * @param {string} answers.interactionMode    - "observe" | "help" | "touch"
 * @returns {Promise<Array>} Array of job objects from the database
 */

import { getMockJobs } from './mocks/jobs.mock';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
const USE_MOCK = String(import.meta.env.VITE_USE_MOCK ?? 'false').toLowerCase() === 'true';
const MOCK_MODE = import.meta.env.VITE_MOCK_MODE ?? 'default';
const MOCK_DELAY_MS = Number(import.meta.env.VITE_MOCK_DELAY_MS ?? 600);

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function fetchJobs(answers) {
  if (USE_MOCK) {
    await wait(MOCK_DELAY_MS);
    return getMockJobs(MOCK_MODE);
  }

  const response = await fetch(`${API_BASE}/api/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(answers),
  });

  if (!response.ok) {
    throw new Error(`API error ${response.status}`);
  }

  const jobs = await response.json();
  return jobs.map((job, i) => ({ ...job, id: job.id ?? i + 1 }));
}
