# IdlerDream 项目进度与资产状态审查

审查日期：2026-08-09
审查方式：仓库只读审查 + 本地重新执行验证命令
审查范围：git 分支/历史、里程碑进度、资产清单一致性、发布就绪状态、验证结果复核

---

## 1. 结论摘要

| 维度 | 状态 |
|---|---|
| 自动化验证（本次重新执行） | ✅ 全部通过（详见 §5） |
| 里程碑 M0–M2 | ✅ 完成（M0 的 Ruff 欠账已于 CR21 阶段清零） |
| 里程碑 M3–M7 | ⚠️ 部分完成（详见 §3） |
| 真机 OpenCode 巡检（Gate C/D/E） | ✅ 通过（OpenCode 1.18.12 + `opencode-go/deepseek-v4-flash`） |
| 发布就绪 | ⛔ 未达发布标准：CR-19/20/21/22 的 Windows 端到端验证 + CR-24 clean-VM 仍为 blocker |
| **仓库健康（本次审查新发现）** | ⚠️ **本地 `main` 与真实历史脱节**（wip 替代历史线根，与 origin/main 无共同祖先，详见 §7.1） |
| 待办外部动作 | PR #21 未合并、issues #19/#20 未关闭、无 tag、无签名证书 |

---

## 2. 仓库与分支状态

### 2.1 分支拓扑（本次审查核实）

```
origin/main (62ed7a6, PR #18 已合并)
   └─ 863edf7  feat: filtered-snapshot inspection reliability (#19 #20)   ← 未合并
       └─ 590fa5b test: portable executable-resolution                     ← 未合并
           └─ 6d026fe fix: PR #21 CodeReview follow-up (CR21-01..10)      ← 未合并 + 未推送
               = 本地 fix/inspection-real-machine-reliability (HEAD)

本地 main (815d2d1 "initial commit")  ← 与 origin/main 无共同祖先；是 wip/overlay-local-history 替代历史线的根（见 §7.1）
```

- 当前分支：`fix/inspection-real-machine-reliability`，工作树干净。
- **未推送**：`6d026fe`（CR21 修复包，本地领先 `origin/fix/inspection-real-machine-reliability` 1 个提交）。
- **未合并到 origin/main**：`863edf7`、`590fa5b`、`6d026fe` 共 3 个提交（PR #21）。
- 无任何 git tag；npm 侧版本号仍为 `0.1.0-dev`（sidecar `pyproject.toml` 已是 0.1.0）。
- 存在 1 个 stash（`reasonix-before-merge`），内容仅为 `.reasonix/` 桌面会话元数据，与代码无关。
- 分支树上遗留大量 `ao/idlerdream-*/` 历史工作分支（实测本地 28 个、远端 5 个，`git for-each-ref` 清点），其中多数已过时，可考虑清理。

### 2.2 历史时间线

| 提交 | 内容 |
|---|---|
| `302dcb9` | bootstrap：已评审的 IdlerDream 资产基线（CR-01..CR-13 修复） |
| `ab95909` | 里程碑 1：单项目手动巡检切片（P1.1 + CR-14/16/17/18） |
| `a3ee689` | CR-24：PyInstaller 打包经 launcher.py 启动修复 |
| `80db2de` | CR-24：CI Windows NSIS 安装/卸载 smoke（`windows-installer` job） |
| `465dd0a` | v0.1 发布材料（release notes/checklist） |
| `62ed7a6` | PR #18：CR-19..CR-22 代码部分（raw storage、monitoring、processes、pipe ACL） |
| `863edf7` | issues #19/#20：过滤快照 + 巡检可靠性 overlay |
| `590fa5b` | test：跨 CI 平台可移植的可执行文件解析测试 |
| `6d026fe` | PR #21 CodeReview follow-up：CR21-01..CR21-10 |

---

## 3. 里程碑进度（对照 docs/IMPLEMENTATION_PLAN.md）

| 里程碑 | 状态 | 说明 |
|---|---|---|
| M0 仓库健康 | ✅ 完成 | sidecar 测试/typecheck/build/CI 全绿；Ruff 基线欠账已于 2026-08-08 清零 |
| M1 单项目手动巡检切片 | ✅ 核心完成 | add/list/facts/UI 完成；真机 OpenCode 巡检（Gate C）与报告合并可用 |
| M2 只读策略证明 | ✅ 完成 (2026-08-06) | 过滤快照隔离 + 兼容性探针在 OpenCode 1.18.12 通过 |
| M3 连续本地监控 | ⚠️ 部分 | 监控循环存在；Watchdog 拆分与 Windows 进程关联待做（=CR-20/21） |
| M4 简化自动巡检 | ⚠️ 部分 | 触发器存在；稳定性/冷却测试待生产加固 |
| M5 数据韧性 | ⚠️ 部分 | 周 JSONL + SQLite 重建 + 原始加密存在；DPAPI/压缩待做（=CR-19） |
| M6 桌面与安装器 | ⚠️ 部分 | tray/单实例/重启限制存在；NSIS clean-VM 安装/卸载待做（=CR-24 余项） |
| M7 UI 质量门 | ⚠️ 接近完成 | axe 0 违规、键盘走查、组件测试、截图齐；系统 High Contrast 截图待补 |

---

## 4. 资产状态（对照 docs/AGENT_ASSET_MANIFEST.md）

### 4.1 清单内资产实际状态

| 资产 | 清单声称 | 实际核实 |
|---|---|---|
| 共享协议 `packages/protocol/` | 可复用 | ✅ 存在；`dist/` 已构建，TS/Python 对齐（`considered_paths`、`inspection_quality` 等） |
| Python 模型与合并逻辑 `models.py`/`state/merger.py` | 可复用 | ✅ 存在；状态合并遵循证据优先级，v2 schema 迁移有测试 |
| 确定性采集器 `collectors/{vcs,tests,files,processes}.py` | 可用但需加固 | ✅ 存在；进程工作目录检测/真 watcher 调度仍待加固（CR-20/21） |
| 巡检适配器 `inspection/opencode.py` 等 | 需真机验证 | ✅ 已真机验证（Gate C/D/E + CR21 加固：独立 Run Profile、模型事实降级、secret 扫描） |
| 存储 `database.py`/`storage/*` | 基础可用 | ✅ 存在；DPAPI 加密存储与周压缩未完成（CR-19） |
| 桌面前端 `apps/desktop/` | 高保真外壳 + mock 回退 | ✅ 存在；mock 仅构建期显式启用（CR-03 修复），UI 测试 9 通过 |
| 设计与规范文档 | 可复用 | ✅ 全部存在（MASTER.md、PRODUCT_SPEC 等） |

### 4.2 资产清单缺口优先级核对

| 优先级 | 状态 |
|---|---|
| P0-1 OpenCode Windows 非交互 JSON 输出 | ✅ 已真机验证 |
| P0-2 项目配置不可覆盖只读策略 | ✅ 快照隔离 + CR21-01/02/09 加固 |
| P0-3 Windows 进程树取消 | ✅ 等价实现：CTRL_BREAK + `CREATE_NEW_PROCESS_GROUP`，OSError 回退进程树终止（CR21-06，真机验证） |
| P0-4 巡检前后指纹失效 | ✅ 快照 hash 验证 |
| P0-5 Windows Credential Manager / DPAPI | ❌ 未完成（CR-19） |
| P1 首个垂直切片（add/facts/inspect/merge/snapshot/render） | ✅ 全部完成 |
| P2 监控循环（watcher/节流/触发/冷却） | ⚠️ 部分 |
| P3 桌面加固（tray/重启限制/单实例/NSIS） | ⚠️ 部分：前四项完成；NSIS clean-VM 待做 |
| P4 无障碍与视觉 QA | ⚠️ 大部分完成：axe 0、键盘走查、截图、明暗主题通过；系统 High Contrast 待做 |

---

## 5. 本次重新执行的验证结果（2026-08-09，Windows / Python 3.14.6 / Node 24.17.0）

| 命令 | 结果 |
|---|---|
| `python -m pytest apps/sidecar/tests` | ✅ 101 passed, 1 skipped（skip = off-Windows TCP fallback） |
| `python -m ruff check apps/sidecar/idlerdream apps/sidecar/tests apps/sidecar/launcher.py` | ✅ All checks passed |
| `python scripts/verify_assets.py` | ✅ asset verification passed |
| `npm run typecheck` | ✅ 通过（protocol + desktop + electron） |
| `npm run test:ui` | ✅ 9 passed（2 个测试文件） |
| `npm run build` | ✅ vite build + electron-builder win-unpacked，exit 0 |
| 打包 Sidecar exe | ✅ 存在 `apps/sidecar/dist/idlerdream-sidecar.exe`（37 MB，2026-08-06 构建） |

本次实测结果与 6d026fe 提交记录一致（101 passed / 1 skipped）。注意：`docs/VALIDATION_REPORT.md` 2026-08-08 段仍记录 97 passed / 1 skipped（590fa5b 时点），尚未同步到 101（同源滞后问题见 §7.4）。CI 使用 Python 3.12 / Node 22，本地为 3.14.6 / 24.17.0，跨版本结果一致。

---

## 6. 发布就绪状态（对照 docs/RELEASE_READINESS.md）

| Gate | 状态 | 备注 |
|---|---|---|
| Gate A 聚焦自动化 | ✅ PASS | 34 focused + 全套件通过 |
| Gate B 全仓库 CI | ⚠️ PARTIAL | 代码全绿；NSIS clean-VM 安装/卸载仍为 CR-24 blocker |
| Gate C OpenCode 兼容 | ✅ PASS | OpenCode 1.18.12 + `opencode-go/deepseek-v4-flash` |
| Gate D 10 次稳定性 | ✅ PASS | 10/10 |
| Gate E 项目矩阵 | ✅ PASS | 5/5（含恶意 fixture、中文路径、非 Git 目录） |
| Gate F UI 质量 | ⚠️ 接近完成 | 系统 High Contrast 截图待补 |

**官方决定（RELEASE_READINESS.md 2026-08-08）：不创建 `v0.1.0-rc.1`。** 剩余 blocker：CR-19（DPAPI/压缩）、CR-20（监控调度拆分）、CR-21（Windows 进程关联）、CR-22（管道 ACL 负向测试）、CR-24 余项（clean-VM tray 生命周期 + 崩溃恢复）。

CI（`.github/workflows/ci.yml`）含 4 个 job：`sidecar`（ubuntu）、`desktop`（windows）、`sidecar-packaging`（PyInstaller + packaged smoke）、`windows-installer`（NSIS 构建 + 静默安装/卸载 smoke + 上传安装包）。已覆盖 CR21-07（`test:ui` 入 CI）。

---

## 7. 本次审查发现的问题与风险

### 7.1 🔴 本地 `main` 分支是孤儿提交（仓库健康）

- 本地 `main` 指向 `815d2d1 "initial commit"`，与 `origin/main`（`62ed7a6`）**无共同祖先**（`git merge-base` 失败）。
- 本地 `main` 落后 `origin/main` 7 个提交，且历史完全脱节——任何人 `git checkout main` 会看到与真实项目无关的空壳仓库。
- **背景**：`815d2d1` 并非凭空产生，而是 `wip/overlay-local-history` 替代历史线的根（该线含 `b09a263`→`070e6c6` 等早期实现提交；从提交内容看疑为被 `302dcb9` 基线重建所取代的旧线，两线在 git 中平行、无共同祖先，先后关系无法从提交图证实；stash 同源）。重置 `main` 前应先评估该线是否仍需保留（如确认弃用，可直接 `git branch -f main origin/main` 或删除重建本地 main）。此操作会移动本地分支指针，需用户确认后执行。

### 7.2 🟠 PR #21 未合并、`6d026fe` 未推送

- `origin/main` 落后当前分支 3 个提交；`origin/fix/inspection-real-machine-reliability` 落后本地 1 个提交（`6d026fe`）。
- 文档明确：合并 PR / 关闭 issues #19/#20 属外部动作，需用户授权。

### 7.3 🟠 CHANGELOG.md 未同步近期工作

- `CHANGELOG.md` 的 `[Unreleased]` 仅列出 remaining work，未记录 #19/#20 可靠性 overlay 与 CR21-01..10 修复（对比 README/RELEASE_READINESS 均已同步）。建议合并前补记。

### 7.4 🟡 其他

- 无 Authenticode 签名证书（文档已诚实标注，installer 231 MB 未签名）。`docs/acceptance/INSPECTION_ACCEPTANCE_2026-08-06.md:133` 正文仍称 "signed"，但同文件 136–137 行 Errata (CR21-08) 已声明未签名——内部勘误已覆盖，无残留矛盾。
- 兼容性矩阵仅覆盖 OpenCode 1.18.12 单一版本、单一模型；新版本不自动继承验证状态（矩阵本身已声明此规则）。
- 遗留 28 个本地 + 5 个远端 `ao/idlerdream-*` 历史分支可清理（`git for-each-ref` 清点）。
- 发布清单 §4 的"预期测试数（30 passed）"已过时，实际为 101 passed, 1 skipped；`docs/VALIDATION_REPORT.md` 2026-08-08 段与 `docs/RELEASE_READINESS.md` 同样滞后（仍记录 97/1，实测 101/1）。

---

## 8. 建议的下一步（按优先级）

1. **修复本地 main 孤儿分支**（7.1，用户确认后一行命令）。
2. 推送 `6d026fe` 并完成 PR #21 合并；更新 CHANGELOG（7.3）。
3. 按发布清单推进剩余 blocker：CR-19（DPAPI 端到端 + 周压缩）、CR-20（监控调度拆分）、CR-21（Windows 进程关联 fixtures）、CR-22（管道 ACL 负向测试）、CR-24（clean-VM tray + 崩溃恢复）。
4. Gate F 收尾：系统 High Contrast 会话下截图。
5. 全部 blocker 绿后执行 `docs/RELEASE_CHECKLIST.md` §3–§6（版本 bump → 最终验证 → tag v0.1.0 → release）。

---

## 9. 范围声明

本次为只读审查 + 重新执行验证，未修改任何代码/文档（本报告除外），未执行任何外部动作（推送、合并、tag、release）。
