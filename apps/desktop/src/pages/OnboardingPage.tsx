import { useMemo, useState } from "react";
import type { CompatibilityResult, InspectorStatus } from "@idlerdream/protocol";
import {
  addProject,
  discoverProjects,
  fetchInspectorStatus,
  pickDirectory,
  setInspectorCredential,
  testInspectorCompatibility,
  updateInspectorConfig,
} from "../lib/api";
import { Icon } from "../lib/icons";

interface OnboardingPageProps {
  onComplete(): void;
}

const steps = ["检测 OpenCode", "配置模型 API", "只读隔离测试", "添加首个项目"];

interface Candidate {
  path: string;
  name: string;
  markers: string;
}

export function OnboardingPage({ onComplete }: OnboardingPageProps) {
  const [step, setStep] = useState(0);
  const [apiKey, setApiKey] = useState("");
  const [revealKey, setRevealKey] = useState(false);
  const [provider, setProvider] = useState("deepseek");
  const [modelId, setModelId] = useState("deepseek/deepseek-v4-flash");
  const [baseUrl, setBaseUrl] = useState("https://api.deepseek.com/v1");
  const [workspace, setWorkspace] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<InspectorStatus | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [compatResult, setCompatResult] = useState<CompatibilityResult | null>(null);
  const [compatError, setCompatError] = useState<string | null>(null);
  const [flowError, setFlowError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const detectOpenCode = async () => {
    setBusy(true);
    setHealthError(null);
    try {
      setHealth(await fetchInspectorStatus());
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
    setFlowError(null);
    try {
      if (step === 0 && !health) await detectOpenCode();
      if (step === 1) {
        // CR-15: persist non-sensitive settings; the API key goes straight to
        // the credential store and is cleared from renderer state immediately.
        await updateInspectorConfig({ provider, base_url: baseUrl, model: modelId });
        if (apiKey) {
          await setInspectorCredential(provider, apiKey);
          setApiKey("");
        }
      }
      if (step === 2) {
        setCompatError(null);
        try {
          setCompatResult(await testInspectorCompatibility());
        } catch (error) {
          setCompatError(error instanceof Error ? error.message : String(error));
        }
      }
      if (step === 3 && workspace && !candidates.length) await scanWorkspace();
      if (step === steps.length - 1) {
        await finish();
        return;
      }
      setStep((value) => value + 1);
    } catch (error) {
      setFlowError(error instanceof Error ? error.message : String(error));
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
                <input value={health?.opencode_executable ?? (health?.opencode_available ? "opencode（已在 PATH）" : "未检测到 opencode")} readOnly />
              </label>
              <div className="setup-result">
                {healthError ? (
                  <div><Icon name="alert" /><span>检测失败：{healthError}</span></div>
                ) : health ? (
                  <div><Icon name="check" /><span>OpenCode {health.opencode_version ?? "（版本未知）"} 可用</span></div>
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
                <span>Provider</span>
                <input value={provider} onChange={(event) => setProvider(event.target.value)} placeholder="例如 deepseek、openai" />
              </label>
              <label>
                <span>Base URL</span>
                <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} />
              </label>
              <label>
                <span>模型 ID</span>
                <input value={modelId} onChange={(event) => setModelId(event.target.value)} placeholder="provider/model 格式，例如 deepseek/deepseek-v4-flash" />
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
              <p className="form-note">密钥只写入系统凭据存储，不进入数据库、日志或项目目录；保存后立即从页面状态清除。</p>
            </div>
          )}

          {step === 2 && (
            <div className="setup-form">
              {compatResult ? (
                compatResult.status === "verified" ? (
                  <>
                    <div className="isolation-checks">
                      <div><Icon name="check" /><span>编辑与写文件工具被拒绝</span></div>
                      <div><Icon name="check" /><span>敏感文件读取被本地规则拒绝</span></div>
                      <div><Icon name="check" /><span>诱导仓库巡检前后指纹一致</span></div>
                      <div><Icon name="check" /><span>项目插件、MCP 与 instructions 已隔离</span></div>
                    </div>
                    <div className="setup-result">
                      <div><Icon name="shield" /><span>当前配置通过只读兼容性测试，深度巡检已启用</span></div>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="setup-result setup-result--error">
                      <div><Icon name="alert" /><span>只读兼容性测试未通过</span></div>
                      {compatResult.error && <small>{compatResult.error}</small>}
                      {compatResult.warnings.length > 0 && (
                        <ul>
                          {compatResult.warnings.map((warning) => (
                            <li key={warning}>{warning}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                    <p className="form-note">仍可使用仅本地监控，但深度巡检将被禁用，直到测试通过。</p>
                  </>
                )
              ) : (
                <div className="setup-result">
                  <div>
                    <Icon name="shield" />
                    <span>{compatError ? `测试失败：${compatError}` : "尚未执行只读隔离测试"}</span>
                  </div>
                  <small>点击「继续」将在隔离的临时目录中运行真实 OpenCode，不会触碰你的项目。</small>
                </div>
              )}
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

          {flowError && (
            <div className="setup-result setup-result--error">
              <div><Icon name="alert" /><span>{flowError}</span></div>
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
