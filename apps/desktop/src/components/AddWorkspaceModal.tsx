import { useEffect, useState } from "react";
import { addProject, discoverProjects, pickDirectory } from "../lib/api";
import { Icon } from "../lib/icons";

interface AddWorkspaceModalProps {
  onClose(): void;
  onAdded(): Promise<void>;
  onError(message: string): void;
}

interface Candidate {
  path: string;
  name: string;
  markers: string;
}

export function AddWorkspaceModal({ onClose, onAdded, onError }: AddWorkspaceModalProps) {
  const [directory, setDirectory] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [selected, setSelected] = useState<Candidate | null>(null);
  const [adding, setAdding] = useState(false);

  const chooseDirectory = async () => {
    const picked = await pickDirectory();
    if (!picked) return;
    setDirectory(picked);
    setSelected(null);
    setCandidates([]);
  };

  useEffect(() => {
    if (!directory) return;
    let disposed = false;
    const discover = async () => {
      setDiscovering(true);
      try {
        const result = await discoverProjects(directory);
        if (disposed) return;
        setCandidates(result.candidates.filter((item) => item.path !== directory));
      } catch (error) {
        if (!disposed) onError(error instanceof Error ? error.message : String(error));
      } finally {
        if (!disposed) setDiscovering(false);
      }
    };
    void discover();
    return () => {
      disposed = true;
    };
  }, [directory, onError]);

  const confirm = async () => {
    const target = selected ?? (directory ? { path: directory, name: directory.split(/[\\/]/).pop() ?? directory, markers: "" } : null);
    if (!target) return;
    setAdding(true);
    try {
      await addProject(target.path, target.name);
      await onAdded();
      onClose();
    } catch (error) {
      onError(error instanceof Error ? error.message : String(error));
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="add-workspace-title">
        <header className="modal-header">
          <div>
            <span className="eyebrow">Add workspace</span>
            <h2 id="add-workspace-title">添加工作区</h2>
            <p>选择本地 Windows 目录，或在目录中发现候选项目后确认监控。</p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭">
            <Icon name="close" />
          </button>
        </header>

        <div className="setup-form">
          <label>
            <span>工作区目录</span>
            <div className="password-field">
              <input value={directory} onChange={(event) => { setDirectory(event.target.value); setCandidates([]); setSelected(null); }} placeholder="选择或输入目录路径" />
              <button type="button" onClick={() => void chooseDirectory()}>浏览…</button>
            </div>
          </label>

          {directory && (
            <div className="workspace-candidates">
              <span className="eyebrow">发现候选项目</span>
              {discovering ? (
                <p className="empty-inline">正在扫描候选项目…</p>
              ) : candidates.length === 0 ? (
                <p className="empty-inline">未发现嵌套项目，将直接监控所选目录。</p>
              ) : (
                <ul className="candidate-list">
                  {candidates.map((item) => (
                    <li key={item.path}>
                      <button
                        type="button"
                        className={selected?.path === item.path ? "active" : ""}
                        onClick={() => setSelected(item)}
                      >
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
              )}
            </div>
          )}
        </div>

        <footer className="modal-actions">
          <button className="button button--secondary" onClick={onClose}>取消</button>
          <button className="button button--primary" onClick={() => void confirm()} disabled={!directory || adding}>
            {adding ? "正在添加…" : "确认添加"}
          </button>
        </footer>
      </section>
    </div>
  );
}
