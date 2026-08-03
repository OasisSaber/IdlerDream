import { useEffect, useState } from "react";
import type { Project } from "@idlerdream/protocol";
import { fetchRemovedProjects, purgeProject, restoreProject } from "../lib/api";
import { Icon } from "../lib/icons";

type SettingsSection = "inspector" | "monitoring" | "data" | "application";

const sections: Array<{ id: SettingsSection; label: string }> = [
  { id: "inspector", label: "OpenCode 与模型" },
  { id: "monitoring", label: "监控规则" },
  { id: "data", label: "数据与保留" },
  { id: "application", label: "应用行为" },
];

export function SettingsPage() {
  const [active, setActive] = useState<SettingsSection>("inspector");
  const [launchAtLogin, setLaunchAtLogin] = useState(true);
  const [removed, setRemoved] = useState<Project[]>([]);

  const reloadRemoved = async () => {
    try {
      setRemoved(await fetchRemovedProjects());
    } catch {
      setRemoved([]);
    }
  };

  useEffect(() => {
    void reloadRemoved();
  }, []);

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
              <section className="panel settings-section">
                <div className="panel-title">
                  <div>
                    <span className="eyebrow">Inspector</span>
                    <h2>OpenCode 巡检器</h2>
                  </div>
                  <span className="status-indicator ok"><i />可用</span>
                </div>
                <div className="setting-row">
                  <div>
                    <strong>OpenCode 路径</strong>
                    <span>用于执行非交互只读深度巡检</span>
                  </div>
                  <code title="C:\Users\Oasis\AppData\Roaming\npm\opencode.cmd">
                    C:\Users\Oasis\AppData\Roaming\npm\opencode.cmd
                  </code>
                </div>
                <div className="setting-row">
                  <div>
                    <strong>模型配置档案</strong>
                    <span>API Key 不保存在 IdlerDream 数据库</span>
                  </div>
                  <button className="select-like">
                    deepseek-v4-flash <Icon name="chevron" />
                  </button>
                </div>
                <div className="setting-row">
                  <div>
                    <strong>只读隔离测试</strong>
                    <span>当前 OpenCode 版本通过诱导修改测试</span>
                  </div>
                  <button className="button button--secondary">
                    <Icon name="shield" />重新测试
                  </button>
                </div>
              </section>

              <section className="panel settings-section">
                <div className="panel-title">
                  <div>
                    <span className="eyebrow">Credentials</span>
                    <h2>API 凭据</h2>
                  </div>
                </div>
                <div className="setting-row">
                  <div>
                    <strong>凭据存储</strong>
                    <span>Windows 凭据管理器 · 仅注入巡检子进程</span>
                  </div>
                  <span className="settings-value">已配置</span>
                </div>
                <div className="setting-row">
                  <div>
                    <strong>连通性</strong>
                    <span>最近验证于 2 分钟前</span>
                  </div>
                  <button className="button button--secondary">重新验证</button>
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
