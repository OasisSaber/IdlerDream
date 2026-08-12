import type {
  CompatibilityResult,
  ConnectivityResult,
  InspectionJob,
  InspectorConfig,
  InspectorStatus,
  ProjectEnvelope,
} from "@idlerdream/protocol";
import { mockCompatibilityResult, mockInspectorConfig, mockInspectorStatus, mockJobs, mockProjects } from "../data/mock";

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

export interface SidecarEvent {
  type: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export function subscribeEvents(onEvent: (event: SidecarEvent) => void): () => void {
  if (mockMode || !readToken) return () => {};
  const url = new URL(apiBase);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/api/v1/events";
  url.searchParams.set("token", readToken);
  const socket = new WebSocket(url.toString());
  socket.onmessage = (message) => {
    try {
      const event = JSON.parse(String(message.data)) as SidecarEvent;
      onEvent(event);
    } catch {
      // Ignore malformed frames; the polling fallback reconciles state.
    }
  };
  return () => socket.close();
}

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

export async function fetchRemovedProjects(): Promise<import("@idlerdream/protocol").Project[]> {
  if (mockMode) return [];
  const response = await apiFetch("/api/v1/projects/removed");
  if (!response.ok) throw new Error("无法读取回收站");
  return response.json();
}

export async function removeProject(projectId: string): Promise<unknown> {
  if (mockMode) return { project_id: projectId };
  if (!window.idlerdream) throw new Error("IdlerDream control bridge is unavailable");
  return window.idlerdream.control("project.remove", { project_id: projectId });
}

export async function addProject(path: string, name?: string): Promise<unknown> {
  if (mockMode) return { id: `mock-${path}`, name: name ?? path.split(/[\\/]/).pop() ?? path, path };
  if (!window.idlerdream) throw new Error("IdlerDream control bridge is unavailable");
  return window.idlerdream.control("project.add", { path, ...(name ? { name } : {}) });
}

export async function discoverProjects(root: string): Promise<{ candidates: Array<{ path: string; name: string; markers: string }> }> {
  if (mockMode) return { candidates: [{ path: root, name: root.split(/[\\/]/).pop() ?? root, markers: "demo" }] };
  if (!window.idlerdream) throw new Error("IdlerDream control bridge is unavailable");
  return window.idlerdream.control("project.discover", { root, max_depth: 4 }) as Promise<{ candidates: Array<{ path: string; name: string; markers: string }> }>;
}

export async function pickDirectory(): Promise<string | null> {
  if (mockMode) return null;
  if (!window.idlerdream) throw new Error("IdlerDream Electron bridge is unavailable");
  return window.idlerdream.pickDirectory();
}

export async function restoreProject(projectId: string): Promise<unknown> {
  if (mockMode) return { project_id: projectId };
  if (!window.idlerdream) throw new Error("IdlerDream control bridge is unavailable");
  return window.idlerdream.control("project.restore", { project_id: projectId });
}

export async function purgeProject(projectId: string): Promise<unknown> {
  if (mockMode) return { project_id: projectId };
  if (!window.idlerdream) throw new Error("IdlerDream control bridge is unavailable");
  return window.idlerdream.control("project.purge", { project_id: projectId });
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

// -- CR-15: Inspector configuration, credentials and validation -------------

export async function fetchInspectorStatus(): Promise<InspectorStatus> {
  if (mockMode) return structuredClone(mockInspectorStatus);
  if (!window.idlerdream) throw new Error("IdlerDream control bridge is unavailable");
  return window.idlerdream.control("inspector.status", {}) as Promise<InspectorStatus>;
}

export async function fetchInspectorConfig(): Promise<InspectorConfig> {
  if (mockMode) return structuredClone(mockInspectorConfig);
  if (!window.idlerdream) throw new Error("IdlerDream control bridge is unavailable");
  return window.idlerdream.control("inspector.config.get", {}) as Promise<InspectorConfig>;
}

export async function updateInspectorConfig(config: InspectorConfig): Promise<InspectorConfig> {
  if (mockMode) return structuredClone(config);
  if (!window.idlerdream) throw new Error("IdlerDream control bridge is unavailable");
  return window.idlerdream.control("inspector.config.update", { ...config }) as Promise<InspectorConfig>;
}

export async function setInspectorCredential(provider: string, apiKey: string): Promise<{ configured: boolean }> {
  if (mockMode) return { configured: true };
  if (!window.idlerdream) throw new Error("IdlerDream control bridge is unavailable");
  return window.idlerdream.control("inspector.credential.set", { provider, api_key: apiKey }) as Promise<{ configured: boolean }>;
}

export async function deleteInspectorCredential(provider: string): Promise<{ configured: boolean }> {
  if (mockMode) return { configured: false };
  if (!window.idlerdream) throw new Error("IdlerDream control bridge is unavailable");
  return window.idlerdream.control("inspector.credential.delete", { provider }) as Promise<{ configured: boolean }>;
}

export async function testInspectorConnectivity(provider: string, baseUrl: string, model: string, apiKey = ""): Promise<ConnectivityResult> {
  if (mockMode) return { status: "passed", model, provider, checked_at: new Date().toISOString(), error: null };
  if (!window.idlerdream) throw new Error("IdlerDream control bridge is unavailable");
  return window.idlerdream.control("inspector.connectivity.test", {
    provider,
    base_url: baseUrl,
    model,
    api_key: apiKey,
  }) as Promise<ConnectivityResult>;
}

export async function testInspectorCompatibility(): Promise<CompatibilityResult> {
  if (mockMode) return structuredClone(mockCompatibilityResult);
  if (!window.idlerdream) throw new Error("IdlerDream control bridge is unavailable");
  return window.idlerdream.control("inspector.compatibility.test", {}) as Promise<CompatibilityResult>;
}
