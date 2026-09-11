# CleanSlate.CsGUI 项目规划

> **零阑工坊 (Nuln Studio)** · 产品矩阵：CleanSlate（绿色CLI版）+ CleanSlate.CsGUI（安装GUI版）
> **维护者**：Bohh (@bohh_admin)
> **最后更新**：2026-09-11
> **版本**：v1.0.4（与CleanSlate内核对齐）

---

## 一、项目定位

### 1.1 一句话定义

**CleanSlate.CsGUI = CleanSlate（Python内核）+ C# GUI外壳 + Launcher安装向导**

本质上，"只是给CleanSlate加了一套GUI组件"。不重写清理逻辑，只做封装与交付。

### 1.2 产品矩阵（双轨制）

| 产品 | 形态 | 目标用户 | 技术栈 | 分发方式 |
|------|------|---------|--------|---------|
| **CleanSlate** | 绿色解压版 | 运维/极客/开发者 | Python + CLI | 绿色免安装（zip） |
| **CleanSlate.CsGUI** | 标准安装版 | 普通用户/小白 | C# WinForms + Python Backend | Launcher安装向导 |

**两者共用同一套内核**：`scanner.py`、`cleaner.py`、`config.py`、`Oadmin.py` 完全复用，零修改。

### 1.3 核心价值

- **内核独立**：CLI版守住了开源社区的"极客初心"（绿色便携、可审计）。
- **交付升级**：GUI版拥抱普通用户的"易用需求"（安装向导、图形界面）。
- **架构红利**：内核升级，外壳无损。CleanSlate更新后，CsGUI只需替换Backend Exe即可获得新功能。

---

## 二、整体架构

### 2.1 三层架构

```
┌─────────────────────────────────────────────────────┐
│                  CsUI (C# WinForms)                 │
│  - 图形界面、用户交互、日志窗口、进度展示             │
│  - 通过 HTTP 调用 Backend API                        │
│  - 权限：普通用户（不提权）                          │
└──────────────────────┬──────────────────────────────┘
                       │  HTTP / REST (127.0.0.1:动态端口)
                       │  启动期：Stdin/Stdout 管道（JSON + 日志）
                       ▼
┌─────────────────────────────────────────────────────┐
│            Backend (Python → Nuitka打包Exe)          │
│  - FastAPI 服务                                     │
│  - 封装调用 scanner / cleaner / config               │
│  - 初始化、扫描、清理、补丁系统                      │
│  - 权限：管理员（Manifest requireAdministrator）     │
└──────────────────────┬──────────────────────────────┘
                       │  函数调用（进程内）
                       ▼
┌─────────────────────────────────────────────────────┐
│              内核核心 (Python)                       │
│  scanner.py / cleaner.py / config.py / patches       │
│  封装为独立函数，由 main/main.py 编排调用            │
└─────────────────────────────────────────────────────┘

        ↑ Launcher (C# Native AOT) 负责解压、环境准备、拉起 CsUI
```

### 2.2 进程模型

| 进程 | 职责 | 权限 | 生命周期 |
|------|------|------|---------|
| **Launcher.exe** | 环境检测、运行时安装、解压主程序、启动CsUI | 普通（触发UAC仅安装运行时） | 一次性，启动CsUI后退出 |
| **CsUI.exe** | GUI、API调用、日志显示 | 普通 | 用户打开到关闭 |
| **Backend.exe** | FastAPI服务、清理执行 | **管理员**（UAC弹窗） | 随CsUI启动/关闭 |

### 2.3 权限设计（关键决策）

> **"GUI不提权，底层Exe自己提权"** —— 权限最小化原则

- CsUI 以普通权限运行（避免被杀软误报、避免文件系统重定向问题）。
- Backend 通过 Manifest `requireAdministrator` 在 `Process.Start()` 时触发 UAC。
- Launcher 与 CsUI 均为 `asInvoker`，确保不会弹出两次UAC。

---

## 三、核心架构决策记录

### 3.1 后端自洽（Self-Contained）

**决策**：Backend Exe 启动后自动执行所有初始化工作（创建yaml、目录、加载补丁、扫描），不依赖外部程序准备环境。

**依据**：
- `main.py` 中的初始化逻辑（清理旧备份、加载配置、扫描磁盘、加载补丁）已全部封装为函数。
- 无论被谁调用（CLI双击 / Launcher / CsUI），行为一致。

**好处**：
- Launcher 和 CsUI 职责极轻，只需"把Backend跑起来"。
- 重复启动、异常退出、断点续装均天然支持（幂等设计）。

### 3.2 路径选择策略

**决策**：优先 `D:\ClSl\`，其次其他非系统盘，最后兜底 `C:\ProgramData\NulnStudio\CleanSlate\`。

**已实现**：`config.py` 的 `_find_best_base_dir()` 已实现此逻辑。

**补充规则**：
- D盘空间不足（<1GB）时自动跳过，选空间最大的其他盘。
- 兜底到C盘时，若空间 <2GB，自动进入 `EMERGENCY_MODE`（禁用备份、跳过高危项）。
- 所有路径逻辑由 `config.py` 统一管理，CsUI 无需关心。

### 3.3 安装形态

**决策**：CleanSlate.CsGUI **仅提供安装版，不提供绿色版**。

**理由**：
1. 天然匹配系统级清理操作（需要管理员权限）。
2. 安装向导体验可控（明确告知UAC、快捷方式、卸载）。
3. 减少售后问题（固定 `Program Files` 环境，避免中文/空格路径崩溃）。
4. CleanSlate（原版）继续提供绿色版，覆盖极客用户 —— **双轨互补**。

### 3.4 端口分配

**决策**：端口不硬编码，由 C# 端动态探测可用端口后通过命令行参数传递给 Backend。

**流程**：
1. CsUI 启动 Backend（`--server` 模式）。
2. Backend 初始化完成，通过 Stdout 吐出扫描JSON。
3. CsUI 解析JSON，秒开界面。
4. CsUI 探测可用端口（默认90915，占用则递增）。
5. CsUI 重启 Backend，传入端口：`Backend.exe --server 90916`。
6. Backend 启动 FastAPI，CsUI 连接 API。

**好处**：彻底避免端口冲突（两个CleanSlate实例抢端口的问题）。

### 3.5 数据流设计（Stdout/Stderr 分离）

**决策**：使用管道（重定向标准输出/错误）在Backend与CsUI之间传递数据。

| 流 | 内容 | 用途 |
|----|------|------|
| **Stdout** | 仅一行初始化完成的JSON | CsUI读取后秒开界面 |
| **Stderr** | 所有运行时日志（扫描进度、清理进度、错误、uvicorn访问日志） | CsUI实时显示在日志窗口 |

**关键约束**：
- Python端所有日志打 `sys.stderr` 且 `flush=True`。
- 只有初始化JSON打 `sys.stdout`，不混入任何其他print。
- uvicorn日志重定向到 stderr。

---

## 四、模块详细设计

### 4.1 Launcher（C# Native AOT）

**职责**：环境管家 + 安装向导

**流程**：
1. **欢迎页**：Logo + 软件名 + 版本号 + "开始安装"按钮。
2. **环境检测**：检查 .NET 8 Desktop Runtime、操作系统版本。
3. **运行时安装**（如缺失）：解压内置 `dotnet8.zip` → 静默执行 `/install /quiet` → 等待完成 → 自动重试检测。
4. **准备就绪**：列出待安装组件（CsUI、Backend、清理规则）。
5. **安装进行中**：解压主程序到目标目录（`D:\ClSl\` 或兜底路径），写入版本标记。
6. **完成**："立即启动"按钮 → 启动 CsUI → Launcher 退出。

**关键实现细节**：
- **解压路径**：优先 `D:\ClSl\`，避免解压到 `Program Files`（需要写权限）。
- **避免重复解压**：检查目标目录是否已存在 `CsUI.exe` + 版本匹配，则跳过解压。
- **静默安装**：`Process.Start("dotnet-runtime.exe", "/install /quiet /norestart")` + `UseShellExecute = true`（触发UAC）。
- **幂等性**：支持断点续装/重复运行。
- **绿色vs安装**：不做绿色版，专注安装向导体验。

### 4.2 CsUI（C# WinForms）

**职责**：图形界面、用户交互、API调用、日志显示

**核心界面**：
- **主界面**：磁盘占用进度条、扫描结果列表（名称/大小/风险等级）、一键清理按钮、手动选择清理项。
- **日志窗口**：实时显示Backend日志（通过Stderr管道），支持清空、复制、按级别着色。
- **设置界面**：对应 `config.yaml` 的可视化编辑（开关扫描项、回收站、备份等）。

**关键实现细节**：
- **进程管理**：`Process` 类启动 Backend，重定向 `StandardOutput` / `StandardError`。
- **UI线程安全**：`ErrorDataReceived` 回调在子线程，需用 `Invoke` 切回UI线程更新TextBox。
- **启动流程**：启动Backend → 读Stdout拿JSON → 解析渲染 → 探测端口 → 重启Backend传端口 → 轮询 `/health` → 显示主界面。
- **进程互斥**：Backend启动时创建全局Mutex，CsUI异常退出后重开可检测到。

### 4.3 Backend（Python + FastAPI）

**打包**：Nuitka `--standalone --onefile --windows-disable-console`

**入口设计（双模）**：
- `Oadmin.py`：管理员权限入口（保留，供CLI和API模式共用）。
- `main.py`：
  - `initialize_backend()`：初始化函数（清理旧文件、加载配置、扫描、加载补丁），返回JSON。
  - `run_cli_mode()`：原有CLI菜单逻辑（极客用户）。
  - `run_api_mode()`：API服务模式（GUI调用）。
- `api.py`（新建）：FastAPI 应用定义（也可直接写在 `main.py` 的 `run_api_mode` 内）。

**API 接口设计**：

| 方法 | 路径 | 说明 | 对应内核函数 |
|------|------|------|-------------|
| GET | `/health` | 健康检查 | - |
| GET | `/scan` | 扫描磁盘，返回结果列表 | `get_all_scans()` + 补丁扫描 |
| POST | `/clean` | 执行清理，传入ids数组 | `run_cleaner(item_id)` |
| GET | `/status` | 磁盘状态（总量/已用/剩余/百分比） | `shutil.disk_usage` |
| GET | `/version` | 版本信息 | `VERSION_NUM` / `VERSION_CODE` |
| POST | `/shutdown` | 优雅退出 | - |

**初始化握手协议**：
1. CsUI 启动 `Oadmin.exe --server`。
2. Backend 执行 `initialize_backend()`，日志打 stderr。
3. 初始化完成，仅一行JSON打 stdout。
4. CsUI 读 Stdout → 解析 → 渲染界面。
5. CsUI 探测端口 → 重启 Backend `--server <port>`。
6. Backend 启动 uvicorn，监听 `127.0.0.1:<port>`。

### 4.4 内核核心（Python）

> **不修改任何清理逻辑**，仅确认现有结构满足API化需求。

**现状确认**：
- `scanner.py`：`get_all_scans()` 返回 `Dict`，数据填入 `AppState.data`。
- `cleaner.py`：`run_cleaner(item_id)` 返回 `{"success", "message", "freed_gb"}`。
- `config.py`：`BASE_DIR`、`EMERGENCY_MODE`、路径逻辑、yaml配置加载。
- `Oadmin.py`：权限检测 + 提权 + 调用 `main()`。
- `main.py`：`AppState`、`initialize_backend()` 逻辑、`main()` 菜单编排。

**API化适配**：仅需新建 `api.py`（或 `run_api_mode`），导入现有函数封装即可。

---

## 五、启动序列（完整时序）

```
用户双击 Launcher.exe
  │
  ├─ Launcher (AOT, 普通权限)
  │   ├─ 检测 .NET 8
  │   │   ├─ 存在 → 跳到"解压主程序"
  │   │   └─ 不存在 → 弹窗询问 → 解压 dotnet8.zip → 静默安装 → 重新检测
  │   ├─ 解压主程序到 D:\ClSl\ (或兜底路径)
  │   ├─ 创建快捷方式、写注册表
  │   └─ 启动 CsUI.exe → Launcher 退出
  │
  ├─ CsUI.exe (普通权限)
  │   ├─ 启动 Backend.exe --server (普通权限，Backend自己提权)
  │   │   └─ Backend 触发 UAC 弹窗
  │   │       ├─ 用户同意 → Backend 以管理员运行 → 执行 initialize_backend()
  │   │       └─ 用户拒绝 → Backend 进程退出 → CsUI 捕获异常提示
  │   ├─ 读取 Stdout → 拿到初始化JSON → 渲染主界面（秒开）
  │   ├─ 监听 Stderr → 实时显示日志到日志窗口
  │   ├─ 探测可用端口 → 重启 Backend --server <port>
  │   ├─ 轮询 /health → 确认服务就绪
  │   └─ 用户操作 → 调用 /scan /clean 等 API
  │
  └─ 用户关闭 CsUI → CsUI 调用 /shutdown → Backend 退出
```

---

## 六、开发路线图

### 阶段一：后端API化（当前阶段）

**目标**：让CleanSlate内核能通过HTTP被调用

- [x] 确认内核函数封装完备（`get_all_scans`、`run_cleaner`、`load_patches_from_dir`）
- [x] 确认 `config.py` 路径逻辑稳健
- [x] 确认 `Oadmin.py` 权限模型可用
- [ ] 新建 `api.py`（FastAPI应用 + 接口定义）
- [ ] 改造 `main.py`：抽取 `initialize_backend()` 函数
- [ ] 实现 Stdout/Stderr 分离（日志函数 + JSON输出）
- [ ] 本地测试：CLI模式与API模式均可正常运行
- [ ] Nuitka打包 Backend → 测试无窗口运行

### 阶段二：Launcher安装向导

**目标**：实现环境检测 + 运行时安装 + 主程序部署

- [ ] 创建 C# WinForms 项目（.NET 8）
- [ ] 实现环境检测（.NET 8、OS版本）
- [ ] 实现 .NET 8 运行时静默安装逻辑
- [ ] 实现主程序解压（含路径选择：D:\ClSl\ → 其他盘 → C盘兜底）
- [ ] 实现"避免重复解压"逻辑（版本标记文件）
- [ ] 创建快捷方式、写注册表、卸载入口
- [ ] 界面美化（深色/扁平风格）
- [ ] 发布为 Native AOT 单文件exe

### 阶段三：CsUI图形界面

**目标**：实现完整的用户交互界面

- [ ] 主界面布局（磁盘进度条、扫描结果列表、清理按钮）
- [ ] 后端进程管理（启动/重启/传端口/读管道）
- [ ] 日志窗口（实时显示、着色、清空/复制）
- [ ] 扫描结果展示 + 一键清理 + 手动选择
- [ ] 设置界面（config.yaml可视化编辑）
- [ ] 进度回调（清理进度实时更新 —— 后续可升级WebSocket/SSE）
- [ ] 进程互斥（Mutex）

### 阶段四：联调与发布

**目标**：整体测试 + 首发版本

- [ ] Launcher + CsUI + Backend 端到端联调
- [ ] 权限流程测试（UAC单次弹出、拒绝处理）
- [ ] 路径测试（D盘/E盘/C盘各种组合）
- [ ] 清理逻辑回归测试（对比CLI版结果一致）
- [ ] 补丁系统测试
- [ ] 错误处理与日志完整性检查
- [ ] 打包为最终安装包（Launcher + CsUI + Backend + 运行时）
- [ ] 更新机制（JSON版本检查 + 自动下载新版本安装包）
- [ ] GitHub Releases / Gitee 发布 v1.0.4 GUI版

### 阶段五：未来增强（规划中）

- [ ] 清理进度实时推送（WebSocket / SSE）
- [ ] 多语言支持（i18n）
- [ ] 扫描规则可视化配置
- [ ] 自动更新（Launcher升级模式：覆盖安装，保留配置）
- [ ] 深色/浅色主题切换
- [ ] 清理计划（定时自动清理）

---

## 七、关键约束与注意事项

### 7.1 Python端

1. **日志必须打 stderr 且 `flush=True`**：避免缓冲区导致C#接收延迟。
2. **Stdout 只能有初始化JSON**：任何其他print都会破坏C#的JSON解析。
3. **清理函数中的 `input()` 需处理**：`clean_winsxs()`、`clean_hibernation()` 等含交互确认，API模式下需改为参数控制或默认跳过高危项。
4. **进度反馈**：当前通过日志文本传递进度，后续可改为结构化进度回调（WebSocket）。

### 7.2 C#端

1. **`BeginOutputReadLine()` / `BeginErrorReadLine()` 必须调用**：否则DataReceived事件不触发。
2. **UI更新必须 `Invoke`**：DataReceived回调在子线程，直接改TextBox会抛跨线程异常。
3. **进程退出处理**：监听 `Exited` 事件，Backend异常退出时提示用户。
4. **端口探测**：从90915开始递增，跳过被占用的端口。

### 7.3 权限与路径

1. **避免双UAC**：Launcher与CsUI均为 `asInvoker`。
2. **解压目录写权限**：不要解压到 `Program Files`，优先 `D:\ClSl\`。
3. **数据目录隔离**：`Program Files` 只读 → 日志/缓存放 `ProgramData` 或 `AppData`。
4. **`EMERGENCY_MODE`**：C盘空间<2GB时自动触发，CsUI应显示警告横幅。

---

## 八、文件结构（规划）

```
CleanSlate.CsGUI/
├── Launcher/                # C# Native AOT 安装向导
│   ├── Launcher.csproj
│   ├── Program.cs
│   ├── InstallWizard.cs     # 向导界面逻辑
│   ├── RuntimeInstaller.cs  # .NET运行时安装
│   └── Extractor.cs         # 主程序解压
│
├── CsUI/                    # C# WinForms 主界面
│   ├── CsUI.csproj
│   └── ApiClient.cs         # HTTP API调用封装
│
├── Backend/                 # Python 后端（从CleanSlate原样复制）
│   ├── api.py               # 【新建】FastAPI应用
│   ├── main.py              # 【改造】抽取 initialize_backend()
│   ├── Oadmin.py            # 【不变】权限入口
│   ├── scanner.py           # 【不变】
│   ├── cleaner.py           # 【不变】（处理input()）
│   ├── config.py            # 【不变】
│   └──patches/             # 补丁目录
│
│
├── Shared/                  # 共享定义
│   ├── ApiContracts.cs      # API请求/响应模型（与Python端JSON对齐）
│   └── VersionInfo.cs
│
└── build/                   # 打包脚本
    ├── build_backend.bat    # Nuitka打包Backend
    ├── build_launcher.bat   # AOT发布Launcher
    ├── build_csui.bat       # 发布CsUI
    └── assemble_release.ps1 # 组装最终安装包
```

---

## 九、附录：API 数据模型（对齐现有内核）

### 9.1 扫描结果项（对应 `AppState.data` 的值）

```json
{
  "id": "temp_user",
  "name": "用户临时文件",
  "size_gb": 2.34,
  "risk": "low",
  "detail": "用户临时文件 2.34 GB",
  "can_clean": true
}
```

### 9.2 `/scan` 响应

```json
{
  "status": "ok",
  "total_gb": 15.67,
  "items": [ /* ... 扫描结果项列表 ... */ ]
}
```

### 9.3 `/clean` 请求与响应

```json
// 请求
{ "ids": ["temp_user", "temp_sys", "browser_cache"] }

// 响应
{
  "total_success": 3,
  "total_failed": 0,
  "total_freed_gb": 4.12,
  "details": [
    { "id": "temp_user", "success": true, "freed_gb": 2.34 },
    { "id": "temp_sys", "success": true, "freed_gb": 1.50 },
    { "id": "browser_cache", "success": true, "freed_gb": 0.28 }
  ]
}
```

### 9.4 `/status` 响应

```json
{
  "total_gb": 476.0,
  "used_gb": 320.5,
  "free_gb": 155.5,
  "usage_percent": 67.3
}
```

---

## 十、设计原则（备忘）

> 以下原则贯穿整个项目，任何改动都不得违背：

1. **内核零修改**：所有清理逻辑保持原样，GUI只是封装层。
2. **后端自洽**：Backend能自己初始化、自检、自愈，不依赖外部准备。
3. **权限最小化**：GUI不提权，Backend自己提权，Launcher不双UAC。
4. **数据管道分离**：Stdout=JSON，Stderr=日志，永不混用。
5. **幂等设计**：重复启动、异常退出、断点续装均安全。
6. **双轨互补**：CLI版（绿色）与 GUI版（安装）共存，覆盖全用户群。
7. **配置驱动**：所有行为由 `config.yaml` 控制，CsUI提供可视化编辑。

---

*文档版本：v1.0 | 2026-09-11*
*维护：零阑工坊 (Nuln Studio)*
*License: GPL-3.0*
*文档由AI生成*
