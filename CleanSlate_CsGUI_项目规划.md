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
│  - 命名管道：握手 + 日志流                            │
│  - HTTP / REST：业务调用（127.0.0.1 + Token）         │
│  - 权限：普通用户（asInvoker）                        │
└───────────┬──────────────────────────┬──────────────┘
            │ 命名管道                  │ HTTP + Token
            │ (握手 / 日志)             │ (127.0.0.1:动态端口)
            ▼                          ▼
┌─────────────────────────────────────────────────────┐
│            Backend (Python → Nuitka打包Exe)          │
│  - FastAPI 服务                                     │
│  - 封装调用 scanner / cleaner / config               │
│  - 自建命名管道、自探测端口、自生成Token              │
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
| **Launcher.exe** | 环境检测、运行时安装、解压主程序、启动CsUI | 安装阶段管理员（单次UAC），启动CsUI前降权 | 一次性，启动CsUI后退出 |
| **CsUI.exe** | GUI、API调用、日志显示 | 普通（asInvoker） | 用户打开到关闭 |
| **Backend.exe** | FastAPI服务、清理执行 | **管理员**（runas触发UAC） | 随CsUI启动；父进程心跳自检，父进程退出即自杀 |

### 2.3 权限设计（关键决策）

> **"GUI不提权，底层Exe自己提权"** —— 权限最小化原则

- CsUI 以普通权限运行（避免被杀软误报、避免文件系统重定向问题）。
- Backend 通过 Manifest `requireAdministrator`，由 CsUI 以 `runas` 方式启动，触发一次 UAC。
- Launcher 在安装阶段需要管理员权限（写 HKLM、静默安装 .NET Runtime、创建公共快捷方式），安装完成后启动 CsUI 时降回普通用户；CsUI 本身为 `asInvoker`。

> **关键约束**：`runas` 提权必须搭配 `UseShellExecute = true`，此模式**与匿名 Stdout/Stderr 重定向互斥**（.NET 直接禁止）。因此 CsUI 与 Backend 之间的初始化握手与日志传输统一使用**命名管道**，不使用匿名管道。这是整个通信层设计的基础前提。

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

**决策**：端口不硬编码，由 Backend 内部从 90915 向上探测 127.0.0.1 可用端口，初始化完成后通过命名管道握手 JSON 返回实际端口给 CsUI。**CsUI 不做端口探测，不重启 Backend**。

**流程**：
1. CsUI 生成随机管道名 `CleanSlate_<GUID>`，以 `runas` 启动 `Backend.exe --server --pipe <pipeName> --parent-pid <csuiPid>`。
2. Backend 提权运行，创建命名管道服务端，执行 `initialize_backend()` 完成初始化与磁盘扫描（仅一次）。
3. Backend 从 90915 起探测空闲端口，启动 uvicorn；若绑定失败自动递增重试，直到成功。
4. Backend 生成一次性 Token。
5. Backend 通过命名管道发送握手 JSON（含 `port`、`token`、`version`）作为第一行。
6. CsUI 读取握手 JSON，解析获得端口与 Token。
7. CsUI 轮询 `/health`（带 Token），确认服务就绪后调用业务 API。

**约束**：
- Backend 仅监听 `127.0.0.1`，禁止监听 `0.0.0.0`。
- 命名管道仅承载握手 JSON 与运行时日志，不承载业务数据。
- 全程只启动一次 Backend，杜绝重启导致的重复磁盘扫描。
- 探测端口存在 TOCTOU 竞态，因此真正绑定由 uvicorn 完成，绑定失败自动换端口重试，直到成功才发送握手。

### 3.5 数据流设计（命名管道 + HTTP 双通道）

**决策**：用命名管道传递握手与日志，用 HTTP + Token 传递业务指令。

| 通道 | 内容 | 方向 | 用途 |
|------|------|------|------|
| **命名管道** | 首行握手 JSON + 后续每行日志 JSON | Backend → CsUI | 获取端口与Token，实时显示日志 |
| **HTTP** | 业务 API（/scan /clean /status...） | 双向 | 扫描、清理、状态查询 |

**关键约束**：
- Python 端所有日志封装为单行 JSON 写入命名管道，`flush` 后立即可见。
- 握手 JSON 作为命名管道的**第一行**，且仅一行；后续行全部为日志。
- 业务 API 一律要求 `Authorization: Bearer <token>`，Token 由 Backend 生成、握手返回、仅存活于本次会话。
- uvicorn 访问日志可重定向到 stderr 或直接关闭（避免污染命名管道）。

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
- **权限**：Launcher 在安装阶段以 `requireAdministrator` 运行（单次 UAC），负责安装运行时、写 HKLM、创建公共快捷方式、解压到受保护目录；启动 CsUI 时以 `runas` 降回普通用户身份。
- **解压路径**：优先 `D:\ClSl\`，避免解压到 `Program Files`（需要写权限）。
- **避免重复解压**：检查目标目录是否已存在 `CsUI.exe` + 版本匹配，则跳过解压。
- **静默安装**：`Process.Start("dotnet-runtime.exe", "/install /quiet /norestart")` + `UseShellExecute = true`。
- **幂等性**：支持断点续装/重复运行。
- **绿色vs安装**：不做绿色版，专注安装向导体验。

### 4.2 CsUI（C# WinForms）

**职责**：图形界面、用户交互、API调用、日志显示

**核心界面**：
- **主界面**：磁盘占用进度条、扫描结果列表（名称/大小/风险等级）、一键清理按钮、手动选择清理项。
- **日志窗口**：实时显示 Backend 日志（通过命名管道），支持清空、复制、按级别着色。
- **设置界面**：对应 `config.yaml` 的可视化编辑（开关扫描项、回收站、备份等）。

**关键实现细节**：
- **进程管理**：`Process` 类以 `UseShellExecute = true` + `Verb = "runas"` 启动 Backend（触发 UAC），**不重定向匿名管道**。
- **命名管道客户端**：`NamedPipeClientStream` 连接 `\\.\pipe\<pipeName>`，异步读取首行握手 JSON，后续行作为日志。
- **UI线程安全**：管道读取在后台线程，需用 `Invoke` 切回 UI 线程更新 TextBox。
- **启动流程**：生成管道名 → `runas` 启动 Backend → 连接命名管道 → 读首行握手 JSON（port/token/version）→ 启动日志读取循环 → 轮询 `/health`（带Token）→ 显示主界面。
- **进程互斥**：Backend 启动时创建全局 Mutex；CsUI 异常退出后重开可检测到已有实例，避免重复启动。
- **父进程绑定**：Backend 通过 `--parent-pid` 监控 CsUI，父进程退出后自动清理并退出，避免管理员进程残留。

```csharp
using System.Diagnostics;
using System.IO.Pipes;
using System.Text.Json;

public class BackendHandshake
{
    public string status { get; set; }
    public int port { get; set; }
    public string token { get; set; }
    public string version { get; set; }
}

public class BackendHost
{
    private Process _proc;
    private ApiClient _apiClient;
    private string _pipeName;

    public async Task StartBackend()
    {
        _pipeName = "CleanSlate_" + Guid.NewGuid().ToString("N");

        var psi = new ProcessStartInfo
        {
            FileName = "Backend.exe",
            Arguments = $"--server --pipe {_pipeName} --parent-pid {Environment.ProcessId}",
            UseShellExecute = true,      // 触发 UAC，与匿名管道重定向互斥
            Verb = "runas",
            WindowStyle = ProcessWindowStyle.Hidden
        };
        _proc = Process.Start(psi);

        var pipe = new NamedPipeClientStream(".", _pipeName, PipeDirection.In);
        await pipe.ConnectAsync(timeout: 30000);

        using var reader = new StreamReader(pipe);
        string jsonLine = await reader.ReadLineAsync();
        var handshake = JsonSerializer.Deserialize<BackendHandshake>(jsonLine);

        _apiClient.SetBaseUrl($"http://127.0.0.1:{handshake.port}");
        _apiClient.SetToken(handshake.token);

        _ = Task.Run(() => PumpLogsAsync(reader));   // 后续行全部是日志

        await WaitForHealthReady(timeoutMs: 10000);
    }

    private async Task PumpLogsAsync(StreamReader reader)
    {
        string line;
        while ((line = await reader.ReadLineAsync()) != null)
        {
            // 解析日志 JSON，Invoke 切回 UI 线程
        }
    }
}
```

### 4.3 Backend（Python + FastAPI）

**打包**：Nuitka `--standalone --onefile --windows-disable-console`

**入口设计（双模）**：
- `Oadmin.py`：管理员权限入口（保留，供CLI和API模式共用）。
- `main.py`：
  - `initialize_backend()`：初始化函数（清理旧文件、加载配置、扫描、加载补丁）。
  - `run_cli_mode()`：原有CLI菜单逻辑（极客用户）。
  - `run_api_mode(pipe_name, parent_pid)`：API服务模式（GUI调用）。
- `api.py`（新建）：FastAPI 应用定义，含 Token 校验依赖。

**run_api_mode 内部流程**：

```python
import socket, sys, json, os, secrets, threading, time
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Depends

VERSION_NUM = "1.0.4"

def build_app(token: str) -> FastAPI:
    app = FastAPI()

    def auth(authorization: str = Header(default="")):
        if authorization != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # 其余接口统一挂 dependencies=[Depends(auth)]
    return app

def find_free_port(start: int = 90915) -> int:
    # 仅做候选探测，真正绑定由 uvicorn 完成，失败自动重试
    for port in range(start, 65535):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("未找到可用本地回环端口")

def run_api_mode(pipe_name: str, parent_pid: int):
    # 1. 初始化（日志写管道），仅执行一次
    initialize_backend(log_sink=pipe_writer)

    # 2. 生成 Token
    token = secrets.token_urlsafe(32)
    app = build_app(token)

    # 3. 探测端口 + 启动 uvicorn，绑定失败自动换端口重试
    port = find_free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    while not server.started:
        if t.is_alive() is False:
            port = find_free_port(port + 1)
            server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None))
            t = threading.Thread(target=server.run, daemon=True)
            t.start()
        time.sleep(0.05)

    # 4. 握手 JSON 作为管道第一行
    handshake = {"status": "ok", "port": port, "token": token, "version": VERSION_NUM}
    pipe_writer.write_line(json.dumps(handshake, ensure_ascii=False))

    # 5. 父进程心跳自检，父进程退出即自杀
    while True:
        if not _parent_alive(parent_pid):
            break
        time.sleep(2)
    server.should_exit = True
```

**API 接口设计**：

| 方法 | 路径 | 说明 | 对应内核函数 | 鉴权 |
|------|------|------|-------------|------|
| GET | `/health` | 健康检查 | - | 否 |
| POST | `/scan` | 扫描磁盘，返回结果列表 | `get_all_scans()` + 补丁扫描 | 是 |
| POST | `/clean` | 执行清理，传入 ids 与 `allow_high_risk` | `run_cleaner(item_id)` | 是 |
| GET | `/status` | 磁盘状态（总量/已用/剩余/百分比） | `shutil.disk_usage` | 是 |
| GET | `/version` | 版本信息 | `VERSION_NUM` / `VERSION_CODE` | 是 |
| POST | `/shutdown` | 优雅退出 | - | 是 |

**初始化握手协议**：
1. CsUI 生成管道名，以 `runas` 启动 `Backend.exe --server --pipe <pipeName> --parent-pid <pid>`。
2. Backend 提权运行，创建命名管道服务端，执行 `initialize_backend()`（日志写管道）。
3. Backend 探测端口、启动 uvicorn（绑定失败自动换端口），生成 Token。
4. Backend 将握手 JSON 写入管道第一行。
5. CsUI 读取第一行 → 解析 port/token/version。
6. CsUI 轮询 `/health`（带 Token）确认服务就绪，后续行作为日志实时展示。

### 4.4 内核核心（Python）

> **不修改任何清理逻辑**，仅确认现有结构满足API化需求。

**现状确认**：
- `scanner.py`：`get_all_scans()` 返回 `Dict`，数据填入 `AppState.data`。
- `cleaner.py`：`run_cleaner(item_id)` 返回 `{"success", "message", "freed_gb"}`。
- `config.py`：`BASE_DIR`、`EMERGENCY_MODE`、路径逻辑、yaml配置加载。
- `Oadmin.py`：权限检测 + 提权 + 调用 `main()`。
- `main.py`：`AppState`、`initialize_backend()` 逻辑、`main()` 菜单编排。

**API化适配**：新建 `api.py`（或 `run_api_mode`），导入现有函数封装即可；`cleaner.py` 中带 `input()` 的高危项（如 `clean_winsxs()`、`clean_hibernation()`）在 API 模式下由 `allow_high_risk` 参数控制，默认跳过。

---

## 五、启动序列（完整时序）

```
用户双击 Launcher.exe
  │
  ├─ Launcher (AOT, 安装阶段管理员 · 单次UAC)
  │   ├─ 检测 .NET 8
  │   │   ├─ 存在 → 跳到"解压主程序"
  │   │   └─ 不存在 → 弹窗询问 → 解压 dotnet8.zip → 静默安装 → 重新检测
  │   ├─ 解压主程序到 D:\ClSl\ (或兜底路径)
  │   ├─ 创建快捷方式、写注册表
  │   └─ 以普通用户身份启动 CsUI.exe → Launcher 退出
  │
  ├─ CsUI.exe (普通权限, asInvoker)
  │   ├─ 生成随机管道名 CleanSlate_<GUID>
  │   ├─ 以 runas 启动 Backend.exe --server --pipe <pipeName> --parent-pid <csuiPid>
  │   │   └─ 触发 UAC 弹窗
  │   │       ├─ 用户同意 → Backend 以管理员运行 → 建管道 → initialize_backend()
  │   │       └─ 用户拒绝 → Backend 进程退出 → CsUI 捕获异常提示
  │   ├─ 连接命名管道 → 读首行握手 JSON → 解析 port/token/version
  │   ├─ 后续行作为日志 → 实时显示到日志窗口
  │   ├─ 轮询 /health (带 Token) → 确认服务就绪
  │   └─ 用户操作 → 调用 /scan /clean 等 API (带 Token)
  │
  └─ 用户关闭 CsUI → CsUI 调用 /shutdown → Backend 退出
       （兜底：Backend 心跳检测父进程退出，自行清理）
```

---

## 六、开发路线图

### 阶段一：后端API化（当前阶段）

**目标**：让CleanSlate内核能通过HTTP被调用

- [x] 确认内核函数封装完备（`get_all_scans`、`run_cleaner`、`load_patches_from_dir`）
- [x] 确认 `config.py` 路径逻辑稳健
- [x] 确认 `Oadmin.py` 权限模型可用
- [ ] 新建 `api.py`（FastAPI应用 + Token鉴权依赖）
- [ ] 改造 `main.py`：抽取 `initialize_backend()` 函数
- [ ] 实现命名管道服务端（握手JSON + 日志行）
- [ ] 实现 Backend 内部端口探测（uvicorn 失败自动重试）
- [ ] 实现 Token 生成与校验
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
- [ ] 后端进程管理（runas启动、命名管道连接、日志泵）
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

1. **日志经命名管道输出**：所有日志封装为单行 JSON，写入管道后立即 `flush`，避免 C# 接收延迟。
2. **管道首行只能是握手JSON**：握手 JSON 为第一行，且仅一行；后续行全部为日志。不得混入其他内容。
3. **清理函数中的 `input()` 需处理**：`clean_winsxs()`、`clean_hibernation()` 等含交互确认，API 模式下由 `allow_high_risk` 参数控制，默认跳过高危项。
4. **进度反馈**：当前通过日志 JSON 传递进度，后续可改为结构化进度回调（WebSocket）。
5. **uvicorn 必须后台 daemon 线程运行**：不能阻塞主线程输出握手 JSON；绑定失败需自动换端口重试。
6. **握手 JSON 输出完成不等于 uvicorn 已经完成端口监听**：依赖上层 C# 做 /health 轮询。
7. **父进程心跳自检**：Backend 周期性检查 `--parent-pid` 是否存活，父进程退出后自动清理并退出，避免管理员进程残留。

### 7.2 C#端

1. **命名管道连接超时**：`NamedPipeClientStream.ConnectAsync` 必须设置超时（建议 30s），超时提示后端启动失败。
2. **UI更新必须 `Invoke`**：管道读取回调在子线程，直接改 TextBox 会抛跨线程异常。
3. **进程退出处理**：监听 `Exited` 事件，Backend 异常退出时提示用户。
4. **不再需要 C# 侧端口探测逻辑**：端口由 Backend 决定并通过握手返回。
5. **握手JSON只读第一行**：其余行全部当作日志处理。
6. **/health 健康检查必须设置超时**（建议10s），超时提示后端服务启动失败。
7. **不要尝试重定向匿名管道**：`runas` 提权与 `RedirectStandardOutput` 互斥，使用命名管道替代。

### 7.3 权限与路径

1. **UAC 次数**：Launcher 在安装阶段弹一次 UAC（装运行时/写注册表）；运行阶段 CsUI 以普通权限启动、由 CsUI 以 `runas` 启动 Backend 再弹一次。两者分属不同阶段，不会叠加在同一次操作里。
2. **解压目录写权限**：不要解压到 Program Files，优先 `D:\ClSl\`。
3. **数据目录隔离**：`Program Files` 只读 → 日志/缓存放 ProgramData 或 AppData。
4. **EMERGENCY_MODE**：C盘空间<2GB时自动触发，CsUI应显示警告横幅。
5. **API Token 必须校验**：Backend 以管理员运行并监听 127.0.0.1，任何本机进程都可能访问；`/clean`、`/shutdown` 等敏感接口必须要求 Token，Token 仅通过握手管道下发。
6. **/clean 只接受白名单 id**：绝不允许请求携带任意文件路径，避免提权后门。

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
│   ├── OCs.GUI.cs           # GUI主文件（主窗体/日志窗口/设置界面）
│   ├── BackendHost.cs       # 后端进程管理 + 命名管道通信
│   └── ApiClient.cs         # HTTP API调用封装（含Token）
│
├── Backend/                 # Python 后端（从CleanSlate原样复制）
│   ├── api.py               # 【新建】FastAPI应用 + Token鉴权
│   ├── main.py              # 【改造】抽取 initialize_backend()、run_api_mode()
│   ├── Oadmin.py            # 【不变】权限入口
│   ├── scanner.py           # 【不变】
│   ├── cleaner.py           # 【不变】（处理input()）
│   ├── config.py            # 【不变】
│   ├── patches/             # 补丁目录
│   └── requirements.txt     # 依赖（pyyaml、fastapi、uvicorn等）
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

### 9.1 握手JSON模型（命名管道首行）

```json
{
  "status": "ok",
  "port": 90917,
  "token": "9f3c...",
  "version": "1.0.4"
}
```

### 9.2 日志行模型（命名管道后续行）

```json
{ "level": "info", "msg": "扫描 C:\\Users\\... 2.34 GB" }
```

### 9.3 扫描结果项（对应 `AppState.data` 的值）

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

### 9.4 `/scan` 响应

```json
{
  "status": "ok",
  "total_gb": 15.67,
  "items": [ /* ... 扫描结果项列表 ... */ ]
}
```

### 9.5 `/clean` 请求与响应

```json
// 请求
{
  "ids": ["temp_user", "temp_sys", "browser_cache"],
  "allow_high_risk": false
}

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

### 9.6 `/status` 响应

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
2. **后端自洽**：Backend能自己初始化、自检、自愈，不依赖外部准备；端口、Token、管道均由 Backend 自主决定。
3. **权限最小化**：CsUI 不提权，Backend 自己提权，Launcher 仅在安装阶段提权。
4. **通道分离**：命名管道=握手+日志，HTTP=业务，永不混用。
5. **单次启动**：Backend 只启动一次，杜绝重启导致的重复扫描。
6. **幂等设计**：重复启动、异常退出、断点续装均安全。
7. **双轨互补**：CLI版（绿色）与 GUI版（安装）共存，覆盖全用户群。
8. **配置驱动**：所有行为由 `config.yaml` 控制，CsUI提供可视化编辑。
9. **安全默认**：管理员 API 必须鉴权，`/clean` 只接受白名单 id，高危项默认跳过。

---

*文档版本：v1.0.4 | 2026-09-11*
*维护：零阑工坊 (Nuln Studio)*
*License: GPL-3.0*
*文档由AI生成*