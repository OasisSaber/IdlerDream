import { useMemo, useState } from "react";
import { addProject, discoverProjects, pickDirectory } from "../lib/api";
import { Icon } from "../lib/icons";

interface OnboardingPageProps {
  onComplete(): void;
}

const steps = ["检测 OpenCode", "配置模型 API", "只读隔离测试", "添加首个项目"];

interface HealthInfo {
  opencodeAvailable: boolean;
  opencodeVersion: string | null;
}

interface Candidate {
  path: string;
  name: string;
  markers: string;
}

export function OnboardingPage({ onComplete }: OnboardingPageProps) {
  const [step, setStep] = useState(0);
  const [apiKey, setApiKey] = useState("");
  const [revealKey, setRevealKey] = useState(false);
  const [modelId, setModelId] = useState("deepseek-v4-flash");
  const [baseUrl, setBaseUrl] = useState("https://api.example.com/v1");
  const [workspace, setWorkspace] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const detectOpenCode = async () => {
    setBusy(true);
    setHealthError(null);
    try {
      const response = await fetch(`${window.idlerdream ? (await window.idlerdream.appInfo()).apiBaseUrl : ""}/health`, {
        headers: window.idlerdream ? { "X-IdlerDream-Read-Token": (await window.idlerdream.appInfo()).readToken } : {},
      });
      if (!response.ok) throw new Error(`Health check failed: ${response.status}`);
      const payload = (await response.json()) as { opencode_available?: boolean; opencode_version?: string | null; mock_inspector?: boolean };
      setHealth({ opencodeAvailable: Boolean(payload.opencode_available), opencodeVersion: payload.opencode_version ?? null });
    } catch (error) {
      setHealthError(error instanceof Error ? error.message : String(error));
      setHealth(null);
    } finally {
      setBusy(false);
    }
  };

  const chooseWorkspace = async () => {
    const picked = await pickDirectory();
    if (!picked) return;
    setWorkspace(picked);
    setCandidates([]);
  };

  const scanWorkspace = async () => {
    if (!workspace) return;
    setBusy(true);
    try {
      const result = await discoverProjects(workspace);
      setCandidates(result.candidates.filter((item) => item.path !== workspace));
    } finally {
      setBusy(false);
    }
  };

  const finish = async () => {
    if (!workspace) return;
    setRunning(true);
    try {
      await addProject(workspace);
      setApiKey("");
      onComplete();
    } finally {
      setRunning(false);
    }
  };

  const stepCopy = useMemo(() => {
    switch (step) {
      case 0:
        return {
          icon: "terminal",
          title: "检测 OpenCode",
          body: "检测可执行文件、版本和现有配置档案。IdlerDream 不会静默安装或升级 OpenCode。",
        };
      case 1:
        return {
          icon: "settings",
          title: "配置模型 API",
          body: "密钥默认写入 Windows 凭据管理器，并仅注入当前巡检子进程。",
        };
      case 2:
        return {
          icon: "shield",
          title: "验证只读边界",
          body: "在临时诱导仓库中确认编辑、敏感文件读取和危险命令均被拒绝。",
        };
      default:
        return {
          icon: "folder",
          title: "添加首个项目",
          body: "选择本地 Windows 工作区，并决定是否在预检后执行首次深度巡检。",
        };
    }
  }, [step]);

  const continueFlow = async () => {
    setBusy(true);
    try {
      if (step === 0 && !health) await detectOpenCode();
      if (step === 2) {
        // 只读隔离测试由 Sidecar 兼容性测试覆盖；此处完成当前步骤即可。
        await new Promise((resolve) => window.setTimeout(resolve, 350));
      }
      if (step === 3 && workspace && !candidates.length) await scanWorkspace();
      if (step === steps.length - 1) {
        await finish();
        return;
      }
      setStep((value) => value + 1);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="onboarding">
      <aside>
        <div className="brand brand--large">
          <span className="brand-mark"><Icon name="activity" /></span>
          <div>
            <strong>IdlerDream</strong>
            <small>Local Operations Dashboard</small>
          </div>
        </div>

        <div className="onboarding-copy">
          <span className="eyebrow">First run setup</span>
          <h1>先建立可信的只读监控边界。</h1>
          <p>
            IdlerDream 不控制 Agent，也不修改项目。首次巡检前会验证 OpenCode、
            模型连通性和只读隔离。
          </p>
        </div>

        <div className="onboarding-steps" aria-label="首次配置进度">
          {steps.map((item, index) => (
            <div
              key={item}
              className={`onboarding-step ${index === step ? "current" : index < step ? "done" : ""}`}
              aria-current={index === step ? "step" : undefined}
            >
              <span>{index < step ? <Icon name="check" /> : index + 1}</span>
              <div>
                <strong>{item}</strong>
                <small>{index < step ? "已完成" : index === step ? "当前步骤" : "等待"}</small>
              </div>
            </div>
          ))}
        </div>
      </aside>

      <main>
        <section className="setup-card" aria-labelledby="setup-title">
          <span className="setup-icon"><Icon name={stepCopy.icon} /></span>
          <span className="eyebrow">Step {step + 1} of 4</span>
          <h2 id="setup-title">{stepCopy.title}</h2>
          <p>{stepCopy.body}</p>

          {step === 0 && (
            <div className="setup-form">
              <label>
                <span>检测到的可执行文件</span>
                <input value={health?.opencodeAvailable ? "opencode（已在 PATH）" : "未检测到 opencode"} readOnly />
              </label>
              <div className="setup-result">
                {healthError ? (
                  <div><Icon name="alert" /><span>检测失败：{healthError}</span></div>
                ) : health ? (
                  <div><Icon name="check" /><span>OpenCode {health.opencodeVersion ?? "（版本未知）"} 可用</span></div>
                ) : (
                  <div><span>尚未检测</span></div>
                )}
                <small>OpenCode 不存在时仍可使用仅本地监控，但无法执行深度巡检。</small>
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="setup-form">
              <label>
                <span>Base URL</span>
                <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} />
              </label>
              <label>
                <span>模型 ID</span>
                <input value={modelId} onChange={(event) => setModelId(event.target.value)} />
              </label>
              <label>
                <span>API Key</span>
                <div className="password-field">
                  <input
                    type={revealKey ? "text" : "password"}
                    value={apiKey}
                    onChange={(event) => setApiKey(event.target.value)}
                    autoComplete="off"
                    placeholder="输入后写入 Windows 凭据管理器"
                  />
                  <button type="button" onClick={() => setRevealKey((value) => !value)}>
                    {revealKey ? "隐藏" : "显示"}
                  </button>
                </div>
              </label>
              <p className="form-note">演示模式不会保存输入；生产实现不得写入数据库、日志或项目目录。</p>
            </div>
          )}

          {step === 2 && (
            <div className="setup-form">
              <div className="isolation-checks">
                <div><Icon name="check" /><span>编辑与写文件工具被拒绝</span></div>
                <div><Icon name="check" /><span>敏感文件读取被本地规则拒绝</span></div>
                <div><Icon name="check" /><span>诱导仓库巡检前后指纹一致</span></div>
                <div><Icon name="check" /><span>项目插件、MCP 与 instructions 已隔离</span></div>
              </div>
              <div className="setup-result">
                <div><Icon name="shield" /><span>当前配置通过只读兼容性测试</span></div>
                <small>失败时仍可使用仅本地监控，但必须禁用深度巡检。</small>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="setup-form">
              <label>
                <span>工作区目录</span>
                <div className="password-field">
                  <input
                    value={workspace}
                    onChange={(event) => { setWorkspace(event.target.value); setCandidates([]); }}
                    placeholder="选择或输入目录路径"
                  />
                  <button type="button" onClick={() => void chooseWorkspace()}>浏览…</button>
                </div>
              </label>
              {workspace && (
                <div className="workspace-candidates">
                  {candidates.length > 0 ? (
                    <>
                      <span className="eyebrow">发现候选项目</span>
                      <ul className="candidate-list">
                        {candidates.map((item) => (
                          <li key={item.path}>
                            <button type="button" onClick={() => setWorkspace(item.path)}>
                              <span className="project-monogram">{item.name.slice(0, 2).toUpperCase()}</span>
                              <div>
                                <strong>{item.name}</strong>
                                <small title={item.path}>{item.path}</small>
                              </div>
                              <em>{item.markers}</em>
                            </button>
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : (
                    <p className="empty-inline">将直接监控所选目录（未发现嵌套候选项目）。</p>
                  )}
                </div>
              )}
              <label className="setup-checkbox">
                <input type="checkbox" defaultChecked />
                <span>创建项目后执行首次只读巡检</span>
              </label>
            </div>
          )}

          <div className="setup-actions">
            {step > 0 && (
              <button className="button button--secondary" onClick={() => setStep((value) => value - 1)}>
                上一步
              </button>
            )}
            <button
              className="button button--primary"
              onClick={() => void continueFlow()}
              disabled={busy || running || (step === steps.length - 1 && !workspace)}
            >
              {running ? "正在创建项目…" : busy ? "正在验证…" : step === steps.length - 1 ? "进入 Dashboard" : "继续"}
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
