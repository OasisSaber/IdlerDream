import type { InspectionJob, ProjectEnvelope } from "@idlerdream/protocol";
import { mockJobs, mockProjects } from "../data/mock";

let apiBase = "http://127.0.0.1:38173";
let readToken = "";
const mockMode = import.meta.env.VITE_USE_MOCKS === "1";

function headers(): HeadersInit {
  if (!readToken) throw new Error("IdlerDream read token is unavailable");
  return { "X-IdlerDream-Read-Token": readToken };
}

async function apiFetch(path: string): Promise<Response> {
  return fetch(`${apiBase}${path}`, { headers: headers(), signal: AbortSignal.timeout(5_000) });
}

export async function initClient(): Promise<void> {
  if (mockMode) return;
  if (!window.idlerdream) throw new Error("IdlerDream Electron bridge is unavailable");
  const info = await window.idlerdream.appInfo();
  apiBase = info.apiBaseUrl;
  readToken = info.readToken;

  let lastError: unknown;
  for (let attempt = 0; attempt < 24; attempt += 1) {
    try {
      const response = await apiFetch("/health");
      if (!response.ok) throw new Error(`Sidecar health returned ${response.status}`);
      return;
    } catch (error) {
      lastError = error;
      await new Promise((resolve) => window.setTimeout(resolve, 250));
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Unable to connect to IdlerDream Sidecar");
}

export const isMockMode = () => mockMode;

export async function fetchProjects(): Promise<ProjectEnvelope[]> {
  if (mockMode) return structuredClone(mockProjects);
  const response = await apiFetch("/api/v1/projects");
  if (!response.ok) throw new Error("无法读取项目列表");
  return response.json();
}

export async function fetchProject(id: string): Promise<ProjectEnvelope & { history?: unknown[] }> {
  if (mockMode) {
    const project = mockProjects.find((item) => item.project.id === id);
    if (!project) throw new Error("项目不存在");
    return structuredClone(project);
  }
  const response = await apiFetch(`/api/v1/projects/${encodeURIComponent(id)}`);
  if (!response.ok) throw new Error("无法读取项目详情");
  return response.json();
}

export async function fetchInspections(): Promise<InspectionJob[]> {
  if (mockMode) return structuredClone(mockJobs);
  const response = await apiFetch("/api/v1/inspections");
  if (!response.ok) throw new Error("无法读取巡检队列");
  return response.json();
}

export async function startInspection(projectId: string): Promise<unknown> {
  if (mockMode) return { project_id: projectId, status: "running" };
  if (!window.idlerdream) throw new Error("IdlerDream control bridge is unavailable");
  return window.idlerdream.control("inspection.start", { project_id: projectId, source: "manual" });
}

export async function cancelInspection(jobId: string): Promise<unknown> {
  if (mockMode) return { cancelled: true };
  if (!window.idlerdream) throw new Error("IdlerDream control bridge is unavailable");
  return window.idlerdream.control("inspection.cancel", { job_id: jobId });
}

export async function openFolder(folderPath: string): Promise<void> {
  if (!window.idlerdream) throw new Error("IdlerDream Electron bridge is unavailable");
  await window.idlerdream.openFolder(folderPath);
}
