# IdlerDream v0.1 Assets

IdlerDream 是一个 Windows 本地优先的桌面 Dashboard，用于监控多个代码工作区与本地 Agent 进程，并通过受限的 OpenCode 只读巡检生成项目状态、当前阶段和唯一下一步。

这个资产包不是只有概念文档。先阅读 `ASSET_INDEX.md`，再从主提示词进入开发。它包含一条可继续实现的纵向切片：

- Electron + React + TypeScript 桌面壳与高保真 Dashboard
- Python Sidecar：项目、文件、Git/JJ、测试、进程、状态归并与快照骨架
- OpenCode 非交互巡检适配器与报告解析器
- 版本化 TypeScript/Python 协议与 JSON Schema
- Sidecar 单元测试
- UI/UX Pro Max 工作流下的持久化设计系统
- Apple 风格前端规范与可直接打开的静态演示
- 架构、产品、实施、验收和安全文档
- 交给后续开发 Agent 的主提示词与专项提示词

## 最快查看前端

直接打开：

```text
preview/apple-dashboard.html
```

该预览不依赖 Node.js，包含总览、项目卡片、详情面板和巡检浮层的交互演示。

## 仓库结构

```text
IdlerDream/
├─ apps/
│  ├─ desktop/              Electron + React 前端
│  └─ sidecar/              Python 本地监控服务
├─ packages/protocol/       共享类型与巡检报告 Schema
├─ design-system/           UI/UX Pro Max 风格持久化规范
├─ docs/                    产品、架构、前端与实施文档
├─ prompts/                 开发 Agent 提示词
├─ preview/                 单文件高保真可交互预览
├─ scripts/                 构建与校验脚本
└─ README.md
```


## Code review status

Start implementation from `docs/CODE_REVIEW.md`. The reviewed package fixes the highest-risk inspector, API-authentication and production-mock defects; unresolved production gaps are assigned IDs CR-14 through CR-24.

GitHub repository creation guidance is in `GITHUB_REPOSITORY_SETUP.md`, with an executable PowerShell helper at `scripts/create-github-repo.ps1`.

## 当前已实现

### 前端

- 首次配置向导
- Apple 风格的侧栏、工具栏、材质层级和系统字体
- 首页固定分组与需要操作高亮
- 项目卡片：已验证状态、实时活动、下一步、执行者、置信度、CPU、内存
- 项目详情：事实与推断、验收条件、Git/JJ、测试、Agent 进程树
- 巡检实时浮层与取消入口
- 设置页
- 系统深浅色自适应
- 键盘焦点、44px 控件、减少动态效果和强制颜色模式处理

### Sidecar

- Pydantic 数据模型
- SQLite 当前状态与项目数据骨架
- 文件路径敏感规则和日志脱敏
- Git/JJ 状态采集
- 常见测试报告采集
- Windows Agent 进程树采集骨架
- 工作区指纹
- OpenCode JSON 事件流解析
- 巡检报告校验和状态归并
- 周级 JSONL 快照
- 原始报告加密存储接口
- 只读 HTTP API 和私有控制通道骨架

## 尚需开发 Agent 完成

资产包中的 `docs/AGENT_ASSET_MANIFEST.md` 按模块列出了缺口。主要包括：

- 真正的文件系统增量监听与去抖调度
- Windows 进程工作目录的稳定采集和 Job Object 管理
- OpenCode 当前版本的隔离参数实机验证
- Windows Credential Manager 与 DPAPI 的生产实现
- Named Pipe 控制通道在 Windows 上的完整集成测试
- 项目添加/批量发现 UI 与真实控制命令
- SQLite/JSONL 迁移和恢复流程
- NSIS 安装、托盘图标与全新 Windows 环境验收

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

也可以使用：

```powershell
.\scripts\dev.ps1
```

## 资产校验

当前校验结果见 `docs/VALIDATION_REPORT.md`。


```powershell
python scripts\verify_assets.py
python -m pytest apps\sidecar\tests
```

## 设计方向

界面不是对 macOS 的像素复刻，而是将 Apple 平台中可迁移的原则应用于 Windows Electron 工具：

- 内容优先，装饰克制
- 侧栏负责顶层导航
- 工具栏承载搜索和窗口级操作
- 材质用于建立前后层级，而不是大面积玻璃效果
- 状态通过文字、图标和色彩共同表达
- 深浅色、键盘访问、减少动态和高对比度均视为基础能力

完整规范见：

- `design-system/idlerdream/MASTER.md`
- `docs/DESIGN_SYSTEM.md`
- `docs/FRONTEND_SPEC.md`

## 建议交给 Agent 的入口

主提示词：

```text
prompts/MASTER_IMPLEMENTATION_PROMPT.md
```

要求 Agent 先阅读资产清单、架构和冻结范围，再按纵向切片实现；不得重新扩张为 Agent 编排器或项目管理软件。
