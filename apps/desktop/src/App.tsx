import type { InspectionJob, ProjectEnvelope } from "@idlerdream/protocol";
import { useEffect, useMemo, useState } from "react";
import { InspectionPanel } from "./components/InspectionPanel";
import { DashboardPage } from "./pages/DashboardPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { ProjectPage } from "./pages/ProjectPage";
import { SettingsPage } from "./pages/SettingsPage";
import {
  cancelInspection,
  fetchInspections,
  fetchProjects,
  initClient,
  isMockMode,
  openFolder,
  startInspection,
} from "./lib/api";
import { Icon } from "./lib/icons";

type View = "dashboard" | "project" | "settings";

export default function App() {
  const [onboarded, setOnboarded] = useState(
    () => localStorage.getItem("idlerdream:onboarded") === "1",
  );
  const [view, setView] = useState<View>("dashboard");
  const [projects, setProjects] = useState<ProjectEnvelope[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [jobs, setJobs] = useState<InspectionJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const reload = async () => {
    const [projectData, jobData] = await Promise.all([
      fetchProjects(),
      fetchInspections(),
    ]);
    setProjects(projectData);
    setJobs(jobData);
  };

  useEffect(() => {
    let disposed = false;
    let timer: number | undefined;
    const connect = async () => {
      try {
        await initClient();
        await reload();
        if (disposed) return;
        setConnectionError(null);
        timer = window.setInterval(() => {
          void reload().catch((error: unknown) => {
            if (!disposed) setConnectionError(error instanceof Error ? error.message : String(error));
          });
        }, 5_000);
      } catch (error) {
        if (!disposed) setConnectionError(error instanceof Error ? error.message : String(error));
      } finally {
        if (!disposed) setLoading(false);
      }
    };
    void connect();
    return () => {
      disposed = true;
      if (timer !== undefined) window.clearInterval(timer);
    };
  }, []);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return projects;
    return projects.filter((item) => {
      const searchable = [
        item.project.name,
        item.project.current_cycle?.name,
        item.state?.phase,
        item.state?.summary,
        ...(item.runtime?.agents.map((agent) => agent.name) ?? []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return searchable.includes(normalized);
    });
  }, [projects, query]);

  const selected = projects.find((item) => item.project.id === selectedId) ?? null;
  const runningJob = jobs.find(
    (job) => job.status === "running" || job.status === "queued",
  );
  const runningProject = projects.find(
    (item) => item.project.id === runningJob?.project_id,
  );

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 2_400);
  };

  const inspect = async (projectId: string) => {
    await startInspection(projectId);
    notify("巡检已加入队列");
    await reload();
  };

  const openProject = (projectId: string) => {
    setSelectedId(projectId);
    setView("project");
  };

  if (!onboarded) {
    return (
      <OnboardingPage
        onComplete={() => {
          localStorage.setItem("idlerdream:onboarded", "1");
          setOnboarded(true);
        }}
      />
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="主导航">
        <div className="brand">
          <span className="brand-mark"><Icon name="activity" /></span>
          <div>
            <strong>IdlerDream</strong>
            <small>Local Operations</small>
          </div>
        </div>

        <nav className="primary-nav" aria-label="应用区域">
          <button
            className={view === "dashboard" ? "active" : ""}
            aria-current={view === "dashboard" ? "page" : undefined}
            onClick={() => setView("dashboard")}
          >
            <Icon name="grid" />
            总览
          </button>
          <button
            className={view === "settings" ? "active" : ""}
            aria-current={view === "settings" ? "page" : undefined}
            onClick={() => setView("settings")}
          >
            <Icon name="settings" />
            设置
          </button>
        </nav>

        <div className="sidebar-section">
          <span className="sidebar-label">工作区</span>
          {projects.slice(0, 6).map((item) => (
            <button
              className={`workspace-nav ${selectedId === item.project.id ? "active" : ""}`}
              key={item.project.id}
              aria-current={selectedId === item.project.id && view === "project" ? "page" : undefined}
              onClick={() => openProject(item.project.id)}
            >
              <span>{item.project.name.slice(0, 2)}</span>
              <div>
                <strong>{item.project.name}</strong>
                <small>{item.state?.phase ?? "未巡检"}</small>
              </div>
              {item.state?.needs_user_attention && (
                <i aria-label="需要用户操作" title="需要用户操作" />
              )}
            </button>
          ))}
        </div>

        <div className="sidebar-health" aria-live="polite">
          <div>
            <span className="health-dot" />
            <strong>本地监控正常</strong>
          </div>
          <p>{isMockMode() ? "演示数据模式" : "Sidecar 已连接"}</p>
        </div>
      </aside>

      <main className="app-main">
        <div className="topbar">
          <label className="search">
            <Icon name="search" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索项目、阶段或 Agent"
              aria-label="搜索项目、阶段或 Agent"
            />
          </label>
          <div className="topbar-actions">
            <button
              className="icon-button"
              onClick={() => void reload()}
              aria-label="刷新项目状态"
              title="刷新项目状态"
            >
              <Icon name="refresh" />
            </button>
            <div className="profile-chip" aria-label="当前本地用户 Oasis">
              <span>OS</span>
              <div>
                <strong>Oasis</strong>
                <small>本地用户</small>
              </div>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="loading-screen" role="status">
            <span className="loader" />
            <p>正在连接本地 Sidecar…</p>
          </div>
        ) : connectionError ? (
          <div className="loading-screen connection-error" role="alert">
            <Icon name="alert" />
            <h2>无法连接 IdlerDream Sidecar</h2>
            <p>{connectionError}</p>
            <button className="primary-button" onClick={() => window.location.reload()}>重新连接</button>
          </div>
        ) : view === "dashboard" ? (
          <DashboardPage
            projects={filtered}
            onOpen={openProject}
            onInspect={(projectId) => void inspect(projectId)}
            onAdd={() => notify("添加工作区向导由 Electron Main 与 Sidecar 控制通道接入")}
          />
        ) : view === "project" && selected ? (
          <ProjectPage
            envelope={selected}
            onBack={() => setView("dashboard")}
            onInspect={() => void inspect(selected.project.id)}
            onOpenFolder={() => void openFolder(selected.project.path)}
          />
        ) : (
          <SettingsPage />
        )}
      </main>

      {runningJob && runningProject && (
        <InspectionPanel
          job={runningJob}
          projectName={runningProject.project.name}
          onCancel={() => {
            void cancelInspection(runningJob.id).then(() => {
              notify("正在取消巡检");
              void reload();
            });
          }}
        />
      )}

      {toast && (
        <div className="toast" role="status" aria-live="polite">
          <Icon name="check" />
          {toast}
        </div>
      )}
    </div>
  );
}
