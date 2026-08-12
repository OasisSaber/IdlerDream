import { useCallback, useEffect, useState } from "react";
import type { InspectorConfig, InspectorStatus, Project } from "@idlerdream/protocol";
import {
  deleteInspectorCredential,
  fetchInspectorConfig,
  fetchInspectorStatus,
  fetchRemovedProjects,
  purgeProject,
  restoreProject,
  setInspectorCredential,
  testInspectorCompatibility,
  testInspectorConnectivity,
  updateInspectorConfig,
} from "../lib/api";
import { Icon } from "../lib/icons";

type SettingsSection = "inspector" | "monitoring" | "data" | "application";

const sections: Array<{ id: SettingsSection; label: string }> = [
  { id: "inspector", label: "OpenCode 与模型" },
  { id: "monitoring", label: "监控规则" },
  { id: "data", label: "数据与保留" },
  { id: "application", label: "应用行为" },
];

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "从未";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return "未知";
  }
}

export function SettingsPage() {
  const [active, setActive] = useState<SettingsSection>("inspector");
  const [launchAtLogin, setLaunchAtLogin] = useState(true);
  const [removed, setRemoved] = useState<Project[]>([]);

  // Inspector state (CR-15 functional settings).
  const [status, setStatus] = useState<InspectorStatus | null>(null);
  const [provider, setProvider] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [executable, setExecutable] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const reloadRemoved = async () => {
    try {
      setRemoved(await fetchRemovedProjects());
    } catch {
      setRemoved([]);
    }
  };

  const reloadInspector = useCallback(async () => {
    try {
      const [nextStatus, config] = await Promise.all([fetchInspectorStatus(), fetchInspectorConfig()]);
      setStatus(nextStatus);
      setProvider(config.provider ?? "");
      setBaseUrl(config.base_url ?? "");
      setModel(config.model ?? "");
      setExecutable(config.opencode_executable ?? "");
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : String(error) });
    }
  }, []);

  useEffect(() => {
    void reloadRemoved();
    void reloadInspector();
  }, [reloadInspector]);

  const restore = async (projectId: string) => {
    await restoreProject(projectId);
    await reloadRemoved();
  };

  const purge = async (project: Project) => {
    const confirmed = window.confirm(
      `永久删除项目“${project.name}”及其全部快照与状态？\n此操作不可撤销，工作区目录本身不会被删除。`,
    );
    if (!confirmed) return;
    await purgeProject(project.id);
    await reloadRemoved();
  };

  const saveConfig = async () => {
    setBusy("saving");
    setMessage(null);
    try {
      await updateInspectorConfig({ provider, base_url: baseUrl, model, opencode_executable: executable });
      setMessage({ kind: "ok", text: "巡检器配置已保存。" });
      await reloadInspector();
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : String(error) });
    } finally {
      setBusy(null);
    }
  };

  const saveCredential = async () => {
    if (!provider) {
      setMessage({ kind: "error", text: "请先填写 Provider 名称。" });
      return;
    }
    if (!apiKey) {
      setMessage({ kind: "error", text: "请输入 API Key。" });
      return;
    }
    setBusy("credential");
    setMessage(null);
    try {
      await setInspectorCredential(provider, apiKey);
      setApiKey(""); // CR-15: never retain the key in renderer state.
      setMessage({ kind: "ok", text: "凭据已写入系统凭据管理器。" });
      await reloadInspector();
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : String(error) });
    } finally {
      setBusy(null);
    }
  };

  const removeCredential = async () => {
    const target = provider || status?.provider;
    if (!target) return;
    setBusy("credential");
    setMessage(null);
    try {
      await deleteInspectorCredential(target);
      setMessage({ kind: "ok", text: "凭据已删除。" });
      await reloadInspector();
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : String(error) });
    } finally {
      setBusy(null);
    }
  };

  const verifyConnectivity = async () => {
    setBusy("connectivity");
    setMessage(null);
    try {
      const result = await testInspectorConnectivity(provider, baseUrl, model);
      setMessage(
        result.status === "passed"
          ? { kind: "ok", text: "模型连通性验证通过。" }
          : { kind: "error", text: `连通性验证失败：${result.error ?? result.status}` },
      );
      await reloadInspector();
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : String(error) });
    } finally {
      setBusy(null);
    }
  };

  const rerunCompatibility = async () => {
    setBusy("compatibility");
    setMessage(null);
    try {
      const result = await testInspectorCompatibility();
      setMessage(
        result.status === "verified"
          ? { kind: "ok", text: "只读隔离测试通过，深度巡检已启用。" }
          : { kind: "error", text: `只读隔离测试未通过：${result.error ?? "请检查 OpenCode 与模型配置"}` },
      );
      await reloadInspector();
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : String(error) });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="page settings-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Application settings</span>
          <h1>设置</h1>
          <p>v0.1 只保留核心运行配置，不构建完整模型配置中心。</p>
        </div>
      </header>

      <div className="settings-layout">
        <nav aria-label="设置分类">
          {sections.map((section) => (
            <button
              key={section.id}
              className={active === section.id ? "active" : ""}
              aria-current={active === section.id ? "page" : undefined}
              onClick={() => setActive(section.id)}
            >
              {section.label}
            </button>
          ))}
        </nav>

        <main>
          {active === "inspector" && (
            <>
              {message && (
                <div className={`settings-message settings-message--${message.kind}`}>
                  <Icon name={message.kind === "ok" ? "check" : "alert"} />
                  <span>{message.text}</span>
                </div>
              )}
              <section className="panel settings-section">
                <div className="panel-title">
                  <div>
                    <span className="eyebrow">Inspector</span>
                    <h2>OpenCode 巡检器</h2>
                  </div>
                  <span className={`status-indicator ${status?.opencode_available ? "ok" : ""}`}>
                    <i />{status?.opencode_available ? "可用" : "不可用"}
                  </span>
                </div>
                {status && status.warnings.length > 0 && (
                  <p className="settings-note">
                    {status.warnings.join("；")}。
                  </p>
                )}
                <div className="setting-row">
                  <div>
                    <strong>OpenCode 路径</strong>
                    <span>用于执行非交互只读深度巡检；留空使用 PATH 中的 opencode</span>
                  </div>
                  <input
                    className="settings-input"
                    value={executable}
                    onChange={(event) => setExecutable(event.target.value)}
                    placeholder="opencode"
                  />
                </div>
                <div className="setting-row">
                  <div>
                    <strong>模型配置档案</strong>
                    <span>API Key 不保存在 IdlerDream 数据库</span>
                  </div>
                  <div className="settings-fields">
                    <input
                      className="settings-input"
                      value={provider}
                      onChange={(event) => setProvider(event.target.value)}
                      placeholder="Provider（如 deepseek）"
                    />
                    <input
                      className="settings-input"
                      value={baseUrl}
                      onChange={(event) => setBaseUrl(event.target.value)}
                      placeholder="Base URL"
                    />
                    <input
                      className="settings-input"
                      value={model}
                      onChange={(event) => setModel(event.target.value)}
                      placeholder="provider/model"
                    />
                  </div>
                </div>
                <div className="setting-row">
                  <div>
                    <strong>只读隔离测试</strong>
                    <span>
                      状态：{status?.compatibility_status === "verified" ? "已通过" : status?.compatibility_status === "failed" ? "未通过" : "未验证"}
                      {status?.compatibility_checked_at ? ` · 最近验证于 ${formatTime(status.compatibility_checked_at)}` : ""}
                      {status?.deep_inspection_enabled ? " · 深度巡检已启用" : " · 深度巡检禁用"}
                    </span>
                  </div>
                  <button
                    className="button button--secondary"
                    onClick={() => void rerunCompatibility()}
                    disabled={busy !== null}
                  >
                    <Icon name="shield" />{busy === "compatibility" ? "测试中…" : "重新测试"}
                  </button>
                </div>
                <div className="setting-actions">
                  <button className="button button--primary" onClick={() => void saveConfig()} disabled={busy !== null}>
                    {busy === "saving" ? "保存中…" : "保存配置"}
                  </button>
                </div>
              </section>

              <section className="panel settings-section">
                <div className="panel-title">
                  <div>
                    <span className="eyebrow">Credentials</span>
                    <h2>API 凭据</h2>
                  </div>
                  <span className="settings-value">{status?.credential_configured ? "已配置" : "未配置"}</span>
                </div>
                <div className="setting-row">
                  <div>
                    <strong>Provider 与 API Key</strong>
                    <span>写入 Windows 凭据管理器 · 仅注入巡检子进程</span>
                  </div>
                  <div className="settings-fields">
                    <input
                      className="settings-input"
                      value={provider}
                      onChange={(event) => setProvider(event.target.value)}
                      placeholder="Provider（如 deepseek）"
                    />
                    <input
                      className="settings-input"
                      type="password"
                      value={apiKey}
                      onChange={(event) => setApiKey(event.target.value)}
                      autoComplete="off"
                      placeholder="API Key（保存后立即清除）"
                    />
                  </div>
                </div>
                <div className="setting-row">
                  <div>
                    <strong>连通性</strong>
                    <span>
                      状态：{status?.connectivity_status === "passed" ? "通过" : status?.connectivity_status === "failed" ? "失败" : "未验证"}
                      {status?.connectivity_checked_at ? ` · 最近验证于 ${formatTime(status.connectivity_checked_at)}` : ""}
                    </span>
                  </div>
                  <button
                    className="button button--secondary"
                    onClick={() => void verifyConnectivity()}
                    disabled={busy !== null}
                  >
                    {busy === "connectivity" ? "验证中…" : "重新验证"}
                  </button>
                </div>
                <div className="setting-actions">
                  <button className="button button--primary" onClick={() => void saveCredential()} disabled={busy !== null}>
                    {busy === "credential" ? "保存中…" : "保存凭据"}
                  </button>
                  <button
                    className="button button--danger"
                    onClick={() => void removeCredential()}
                    disabled={busy !== null || !(status?.credential_configured)}
                  >
                    删除凭据
                  </button>
                </div>
              </section>
            </>
          )}

          {active === "monitoring" && (
            <section className="panel settings-section">
              <div className="panel-title">
                <div>
                  <span className="eyebrow">Monitoring</span>
                  <h2>监控规则</h2>
                </div>
              </div>
              <div className="setting-row">
                <div>
                  <strong>默认非活跃阈值</strong>
                  <span>无有效活动后只停止深度分析</span>
                </div>
                <button className="select-like">3 天 <Icon name="chevron" /></button>
              </div>
              <div className="setting-row">
                <div>
                  <strong>后台资源采样</strong>
                  <span>Agent 进程树 CPU 与内存</span>
                </div>
                <button className="select-like">每 10 秒 <Icon name="chevron" /></button>
              </div>
              <div className="setting-row">
                <div>
                  <strong>简化自动巡检</strong>
                  <span>Agent 退出或明确测试结果变化后触发</span>
                </div>
                <label className="switch">
                  <input type="checkbox" defaultChecked />
                  <span />
                </label>
              </div>
            </section>
          )}

          {active === "data" && (
            <>
              <section className="panel settings-section">
                <div className="panel-title">
                  <div>
                    <span className="eyebrow">Data retention</span>
                    <h2>数据与保留</h2>
                  </div>
                </div>
                <div className="setting-row">
                  <div>
                    <strong>原始报告保留期</strong>
                    <span>到期后执行加密销毁</span>
                  </div>
                  <button className="select-like">7 天 <Icon name="chevron" /></button>
                </div>
                <div className="setting-row">
                  <div>
                    <strong>结构化快照</strong>
                    <span>周级 JSONL，只有用户手动删除</span>
                  </div>
                  <span className="settings-value">长期保留</span>
                </div>
                <div className="setting-row">
                  <div>
                    <strong>数据目录</strong>
                    <span>%LOCALAPPDATA%\IdlerDream</span>
                  </div>
                  <button className="button button--secondary"><Icon name="folder" />打开目录</button>
                </div>
              </section>

              <section className="panel settings-section">
                <div className="panel-title">
                  <div>
                    <span className="eyebrow">Recycle bin</span>
                    <h2>回收站（已移除项目）</h2>
                  </div>
                  <span className="status-indicator">{removed.length ? `共 ${removed.length} 项` : "空"}</span>
                </div>
                {removed.length === 0 ? (
                  <p className="empty-inline">没有已移除的项目。移除操作只隐藏项目，工作区目录不会被删除。</p>
                ) : (
                  <ul className="removed-list">
                    {removed.map((project) => (
                      <li key={project.id} className="removed-item">
                        <div>
                          <strong>{project.name}</strong>
                          <span title={project.path}>{project.path}</span>
                        </div>
                        <div className="removed-actions">
                          <button className="button button--secondary" onClick={() => void restore(project.id)}>
                            <Icon name="refresh" />恢复
                          </button>
                          <button className="button button--danger" onClick={() => void purge(project)}>
                            <Icon name="trash" />永久删除
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}

          {active === "application" && (
            <section className="panel settings-section">
              <div className="panel-title">
                <div>
                  <span className="eyebrow">Application</span>
                  <h2>应用行为</h2>
                </div>
              </div>
              <div className="setting-row">
                <div>
                  <strong>开机启动</strong>
                  <span>关闭主窗口后继续在托盘监控</span>
                </div>
                <label className="switch">
                  <input
                    type="checkbox"
                    checked={launchAtLogin}
                    onChange={(event) => setLaunchAtLogin(event.target.checked)}
                  />
                  <span />
                </label>
              </div>
              <div className="setting-row">
                <div>
                  <strong>关闭窗口</strong>
                  <span>隐藏到系统托盘，不终止 Sidecar</span>
                </div>
                <span className="settings-value">缩到托盘</span>
              </div>
              <div className="setting-row">
                <div>
                  <strong>外观</strong>
                  <span>跟随 Windows 系统深浅色设置</span>
                </div>
                <span className="settings-value">跟随系统</span>
              </div>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
