# IdlerDream v0.1

IdlerDream 是一个 Windows 本地优先的只读仪表盘，用于观察多个代码工作区与本地
Agent 进程。它持续收集确定性本地事实，并通过受限的 OpenCode 巡检生成项目的
已验证状态、当前阶段、唯一最高优先级下一步以及责任执行者。

产品对项目工作是只读的：不启动、不停止、不指派、不协调 Agent，也不发送任务。

## 当前里程碑（2026-08-06）

巡检可靠性实施资产包（Issues #19/#20）已集成并通过本机实机验收：

- **Gate A（自动化检查）**：通过 — Sidecar 63 项测试、compileall、资产校验、
  TypeScript 类型检查、Vite/Electron 构建。
- **Gate C（OpenCode 只读策略）**：通过 — OpenCode 1.18.12 +
  `opencode-go/deepseek-v4-flash` 在过滤快照隔离下可读普通源码、敏感文件与
  Agent 控制文件不可见、写/Shell 被拒、快照哈希不变。
- **Gate D（10 次稳定性）**：通过 — 10/10 有效或 partial 报告，项目 ID 与
  工作区指纹全部正确，真实工作区未被修改。
- **Gate E（项目矩阵）**：通过 — 小型 Git 项目、中型仓库、hostile 项目、
  含空格与中文路径、非 Git 目录共 5/5 有效。
- **Gate B（部分）**：Sidecar 已打包并冒烟通过，NSIS 安装器本机构建成功
  （231MB，已签名）；干净虚拟机安装/卸载仍属 CR-24。
- **Gate F（UI 质量）**：接近完成 — 预览页与桌面应用在明/暗模式下 axe
  （wcag2a/2aa/21aa + best-practice）均 0 违规；键盘走查通过；四种尺寸与
  应用三态（full/partial/failed）截图已采集（`output/playwright/`）；真实
  Windows 高对比度会话待补。

详细证据见 `docs/VALIDATION_REPORT.md`、`docs/INSPECTION_COMPATIBILITY.md`、
`docs/RELEASE_READINESS.md`。发布决策前不创建 `v0.1.0-rc.1`。

## 过滤快照巡检

OpenCode 从不接触真实工作区路径，巡检过程为：

```text
真实工作区 → Sidecar 候选清单 → 路径包含性检查 → 敏感/Agent 控制文件排除
→ 文件/内容预算（200 文件、200 KiB/文件、2 MiB 总量）→ UTF-8 规范化临时快照
→ 隔离的 OpenCode HOME/配置 → 仅 read/list/glob/grep → 报告归一化
→ 项目 ID + 指纹校验 → 状态归并
```

硬性排除：`.env*`、密钥/证书、npm/PyPI 凭据、`AGENTS.md`/`CLAUDE.md`/
`GEMINI.md`、`.opencode`/`.claude`/`.codex`/`.cursor`/`.windsurf`、
Copilot 指令文件、符号链接、二进制与超限文件。

## 报告质量

- **FULL**：通过 Schema、项目身份与指纹校验，且无归一化告警。
- **PARTIAL**：至少一处确定性修复或非核心字段丢弃；置信度由 Sidecar 封顶为
  `0.75`，并在 UI 中展示归一化说明。
- **FAILED**：无候选通过硬校验；不覆盖当前已验证状态。

已记录的安全归一化（始终确定性、不发明项目身份/指纹/核心状态）：camelCase
别名、Markdown 围栏提取、平衡对象周围的多余文字、null 数组、百分比置信度、
actor 别名、缺失 phase/summary/next_action、JSON5 风格（未加引号键、单引号
字符串、尾逗号）。

## 已验证环境

- Windows 11（build 26200）、Python 3.14、Node 24、npm 11
- OpenCode 1.18.12（`opencode-ai` npm 包，`bin/opencode.exe`）
- 模型/Profile：`opencode-go/deepseek-v4-flash`

新版本 OpenCode 不会自动继承验证状态，需重跑
`scripts/test-opencode-readonly-policy.ps1`（要求 PowerShell 7）与 10 次稳定性
门禁。

## 仓库结构

```text
IdlerDream/
├── apps/
│   ├── desktop/              Electron + React 前端
│   └── sidecar/              Python 本地监控服务
├── packages/protocol/        共享类型与巡检报告 Schema
├── design-system/            UI/UX 风格持久化规范
├── docs/                     产品、架构、验收与发布文档
├── prompts/                  开发 Agent 提示词
├── preview/                  单文件高保真可交互预览
├── scripts/                  构建与校验脚本
└── fixtures/                 OpenCode 只读策略 hostile fixture
```

## 开发环境

### Node

```powershell
npm install
npm run typecheck
npm run dev
```

### Python Sidecar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".\apps\sidecar[dev]"
python -m pytest apps\sidecar\tests
python -m idlerdream.main
```

也可以使用 `.\scripts\dev.ps1`。

## 资产校验

```powershell
python scripts\verify_assets.py
python -m pytest apps\sidecar\tests
npm run typecheck
npm run build
```

当前结果见 `docs/VALIDATION_REPORT.md`。

## 设计方向

界面不是对 macOS 的像素级复制，而是把 Apple 平台中可迁移的原则应用到 Windows
Electron 工具：内容优先、侧栏负责顶层导航、工具栏承载搜索与窗口级操作、材质用于
建立前后层级、状态通过文字/图标/色彩共同表达、深浅色/键盘访问/减少动效/高对比度
均为基础能力。完整规范见 `design-system/idlerdream/MASTER.md`。

## 明确非目标

- 不做 Agent 任务分发/控制、不做全局跨项目巡检、不做浏览器访问、不做通知
- 不做云端同步、不做项目进度加权百分比、不做备份/恢复与自动更新
