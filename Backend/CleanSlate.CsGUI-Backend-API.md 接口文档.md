# CleanSlate 后端 API 接口文档

> 其实原本没必要写这个东西的

>文档由某豆AI整理生成
---

## 先说几个硬的

- 后端只监听 `127.0.0.1`，端口随机，每次启动都不一样，由 C# 父进程拉起，启动时通过**命名管道**把 `port` 和 `token` 塞给你。
- **几乎所有接口都要带 token**，请求头写 `Authorization: Bearer {token}`，不带或者带错，直接甩你 `401 token无效`。
- 返回都是 JSON。状态码就那几样：`200` 成了、`400` 你参数给错了、`401` 你没资格、`404` 东西不存在、`500` 后端自己炸了。
- 后端必须拿 **Windows 管理员权限** 跑，不然它不干活。

---

## 基础信息

| 项目 | 值 |
|---|---|
| Base URL | `http://127.0.0.1:{port}` |
| 认证方式 | `Authorization: Bearer <token>` |
| Content-Type | `application/json` |

---

## 会用到的基础模型

### 扫描任务对象 `ScanTask`

```json
{
  "status": "pending | running | done | error",
  "progress": 0,
  "result": [],
  "error": null
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | string | `pending` 排队中 / `running` 跑着呢 / `done` 完事 / `error` 挂了 |
| `progress` | int | 进度百分比 0~100 |
| `result` | array | 扫描结果，元素是 `ScanItem` |
| `error` | string/null | 出错时的堆栈文本，没出错就是 null |

### 扫描结果项 `ScanItem`

```json
{
  "id": "temp_sys",
  "name": "系统临时文件",
  "risk": "low",
  "size_gb": 1.23,
  "can_clean": true,
  "detail": "描述文本"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 清理项的唯一标识，后面清理就靠它点名 |
| `name` | string | 给用户看的名字 |
| `risk` | string | 风险等级 `low` / `medium` / `high` |
| `size_gb` | number | 能腾出来的空间（GB） |
| `can_clean` | bool | 能不能清理 |
| `detail` | string | 描述文案 |

### 清理事件 `CleanEvent`

```json
{
  "type": "start | finish | all_done",
  "tid": "task_id字符串",
  "data": {
    "success": true,
    "message": "完成",
    "freed_gb": 0.82
  }
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | string | `start` 开始 / `finish` 一个清完了 / `all_done` 全部清完 |
| `tid` | string | 是哪个清理项触发的事件 |
| `data` | object | 事件详情（success、message、freed_gb 这些） |

### 清理任务返回 `CleanTaskResult`

```json
{
  "status": "running | done",
  "events": []
}
```

> ⚠️ 重点！`events` 是**一次性消费**的：你 GET 一次，服务端就把这批事件清了，下次再来只有新产生的。想拿全就得自己攒着。

---

## 接口一览

### 1. 健康检查

`GET /health`

看看后端是不是还活着。这是唯一不用 token 的接口。

```json
{ "status": "ok" }
```

---

### 2. 提交扫描任务

`POST /scan`

让后端去扫一遍磁盘，是个异步的活。先给你一个 `task_id`，之后轮询下面的接口拿结果。**要 token**，请求体空着就行。

```json
{ "task_id": "uuid-string" }
```

---

### 3. 拿扫描任务的状态和结果

`GET /scan_task/{task_id}`

**要 token**。

**路径参数**：`task_id` —— 扫描任务 id。

成功就返回一个 `ScanTask`，大概长这样：

```json
{
  "status": "done",
  "progress": 100,
  "result": [
    {
      "id": "temp_sys",
      "name": "系统临时文件",
      "risk": "low",
      "size_gb": 0.42,
      "can_clean": true,
      "detail": "系统临时文件 0.42 GB"
    }
  ],
  "error": null
}
```

任务 id 不存在，返回 404：`{ "detail": "task not found" }`

---

### 4. 拿磁盘状态

`GET /status`

C 盘现在啥情况，还剩多少。**要 token**。

```json
{
  "total_gb": 465.21,
  "used_gb": 220.33,
  "free_gb": 244.88,
  "usage_percent": 47.36
}
```

---

### 5. 拿版本信息

`GET /version`

**要 token**。

```json
{
  "version_num": "正式定制版v1.0.5",
  "version_code": 1005,
  "emergency_mode": false
}
```

---

### 6. 提交清理任务

`POST /clean`

让后端去清垃圾，也是异步。普通任务可以并发一起清；但 `winsxs`、`shadow`、`hibernation` 这三个是**串行**的，别想投机。**要 token**。

**请求体**

```json
{ "ids": ["temp_sys", "temp_user", "winsxs"] }
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `ids` | string[] | 要清理的 id 数组，就是扫描结果里那个 `id` |

```json
{ "task_id": "uuid-string" }
```

`ids` 是空的，返回 400：`{ "detail": "未提供清理项" }`

---

### 7. 拿清理任务事件

`GET /clean_task/{task_id}`

**要 token**。再强调一次：这里拿到的 `events` 是**取完就没了**的，适合前端边拿边播进度条。

**路径参数**：`task_id` —— 清理任务 id。

```json
{
  "status": "done",
  "events": [
    { "type": "start", "tid": "temp_sys", "data": {} },
    { "type": "finish", "tid": "temp_sys", "data": { "success": true, "message": "完成", "freed_gb": 0.41 } },
    { "type": "all_done", "tid": "", "data": { "final_result": {} } }
  ]
}
```

任务不存在返回 404：`{ "detail": "task not found" }`

---

### 8. 拿配置

`GET /config`

把 config.yaml 解析成 JSON 给你。**要 token**。

```json
{
  "check_update": false,
  "custom_cache_dirs": [],
  "recycle_bin": { "enabled": false },
  "backup": { "enabled": true, "dir": "D:/ClSl/backup" },
  "aggressive_mode_enabled": false,
  "enable_patch": false,
  "scanner": {
    "temp_sys": true,
    "temp_user": true
  }
}
```

---

### 9. 改配置

`POST /config`

只能改白名单里的字段，改之前会校验备份目录和自定义缓存目录合不合法，然后写回 yaml。**要 token**。

```json
{
  "check_update": true,
  "recycle_bin": { "enabled": true },
  "custom_cache_dirs": ["D:\\mycache"]
}
```

```json
{
  "status": "ok",
  "restart_required": true
}
```

`restart_required: true` 的意思是：改是改上了，但得重启 backend 才真正生效，别指望热更新。

---

### 10. 导出配置

`GET /config/export`

把 config.yaml 原始文本直接给你，方便拿去存档或者对比。**要 token**。

```json
{
  "status": "ok",
  "content": "yaml原始字符串..."
}
```

---

### 11. 导入配置

`POST /config/import`

你把一整份 yaml 塞回来，它先自动备份旧的，再写入，还是只认白名单字段。**要 token**。

```json
{
  "content": "check_update: true\nrecycle_bin:\n  enabled: true\n..."
}
```

```json
{
  "status": "ok",
  "restart_required": true,
  "backup": "D:/ClSl/config.yaml.bak_20260410_153022"
}
```

---

### 12. 拿补丁信息

`GET /patches`

看看补丁目录啥情况、加载了哪些、都有啥文件。**要 token**。

```json
{
  "enable_patch": false,
  "patch_dir": "D:/ClSl/patches",
  "loaded_ids": [],
  "files": [
    { "filename": "test.bcs", "size": 1240, "loaded": false }
  ]
}
```

---

### 13. 导入补丁文件

`POST /patches/import`

传一个补丁（`.bcs` 或 `.py`），内容要 base64 编码，存进补丁目录。存完得重启后端才加载。**要 token**。

```json
{
  "filename": "mypatch.py",
  "content_b64": "base64编码后的文件内容"
}
```

```json
{
  "status": "ok",
  "saved_to": "D:/ClSl/patches/mypatch.py",
  "restart_required": true
}
```

---

### 14. 删补丁

`POST /patches/delete`

删补丁目录里的某个文件。只认文件名，做了路径安全处理，防路径穿越。**要 token**。

```json
{ "filename": "mypatch.py" }
```

```json
{ "status": "ok", "restart_required": true }
```

---

### 15. 优雅关后端

`POST /shutdown`

让它体面地退出：置 shutdown_event，uvicorn 服务退场，父进程心跳检测也会跟着退出。**要 token**。

```json
{
  "status": "shutting_down",
  "msg": "Backend开始执行优雅退出"
}
```

---

## 出错的统一样子

所有 HTTP 异常都是一个结构，看 `detail` 就行：

```json
{
  "detail": "错误描述字符串"
}
```

---

## 启动握手（命名管道，反人类预警）

Python 后端是被 C# 父进程用命令行拉起来的：`--server --pipe {pipename} --parent-pid {pid}`。

流程大概是：

1. Python 把命名管道当输出口，日志和握手消息都往里吐 JSON 行（一行一个 JSON 对象）。
2. 第一条消息就是**握手包**：

```json
{
  "status": "ok",
  "port": 73012,
  "token": "32位secrets.token_urlsafe字符串",
  "version": "正式定制版v1.0.5"
}
```

3. 之后是日志消息：

```json
{ "level": "info|warn|error|debug", "msg": "日志文本" }
```

---

## 调用流程
1. C# 用管理员权限拉起 Python，带上 `--server --pipe xxx --parent-pid xxx`。
2. Python 初始化，向命名管道输出握手包，拿到 `port` 和 `token`。
3. C# 用这俩去调 HTTP 接口，请求头带 `Bearer token`。
4. 扫描：`POST /scan` 拿 `task_id` → 轮询 `GET /scan_task/{task_id}` 直到 `status = done`。
5. 清理：`POST /clean` 带 `ids` 数组拿 `task_id` → 轮询 `GET /clean_task/{task_id}` 消费 `events`。
6. 干完活 `POST /shutdown` 关后端。

---

## 几个别踩的坑

1. `token` 每次启动都重新随机生成，后端一重启就换新的，别写死。
2. `/clean_task/{task_id}` 的 `events` 是消费式的，GET 一次清一次，**别让多个客户端同时轮询同一个任务**，不然会互相抢事件。
3. `winsxs`、`shadow`、`hibernation` 是串行任务，别想着并发。
4. 改配置、导入/删补丁，都得重启 backend 才生效。
5. 后端会盯着父进程（parent-pid），父进程一挂它立刻自己退，防止留个僵尸。

---

> **头铁可以试试对接，但是不建议，因为命名管道握手逻辑有点反人类。**
