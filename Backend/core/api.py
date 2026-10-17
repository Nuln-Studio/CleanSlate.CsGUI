import sys
import socket
import secrets
import threading
import time
import json
import ctypes
import uuid
import queue
from ctypes import wintypes
from core.logutil import set_backend_log_callback
from fastapi import FastAPI, Depends, Header, HTTPException
import uvicorn
from core import Ccore
from core.cleaner import (
    run_cleaner,
    run_cleaner_batch_async,
    set_task_event_queue,
    SERIAL_TASK_IDS
)

_pipe_lock = threading.Lock()


def pipe_open(pipe_name: str) -> int:
    # UAC无法使用stdout，依靠命名管道通信；句柄必须释放
    pipe_full = rf"\\.\pipe\{pipe_name}"
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    h = ctypes.windll.kernel32.CreateFileW(
        pipe_full, GENERIC_WRITE, 0, None, OPEN_EXISTING, 0, None
    )
    invalid = wintypes.HANDLE(-1).value
    if h == invalid:
        raise OSError(f"命名管道打开失败 {pipe_full}，确认C#已创建管道服务端")
    return h


def pipe_write_line(handle: int, obj: dict):
    # C#按换行符解析JSON
    if handle == 0:
        return
    buf = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    written = wintypes.DWORD()
    with _pipe_lock:
        ctypes.windll.kernel32.WriteFile(handle, buf, len(buf), ctypes.byref(written), None)


def pipe_close(handle: int):
    if handle != 0:
        ctypes.windll.kernel32.CloseHandle(handle)


def is_process_alive(pid: int) -> bool:
    PROCESS_QUERY_INFORMATION = 0x0400
    hproc = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
    if not hproc:
        return False
    exit_code = wintypes.DWORD()
    ctypes.windll.kernel32.GetExitCodeProcess(hproc, ctypes.byref(exit_code))
    ctypes.windll.kernel32.CloseHandle(hproc)
    return exit_code.value == 259


def find_free_port(start: int = 72916) -> int:  # 72916幸运数字不要改！！！
    # 优先从起点向高位查找
    for port in range(start, 65535):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    # 高位全部占用，向下兜底查找 10000 ~ start‑1
    for port in range(10000, start):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("无可用本地回环端口")


def start_uvicorn(app):
    # uvicorn会阻塞，必须后台线程
    for _ in range(8):
        port = find_free_port()
        cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None)
        server = uvicorn.Server(cfg)
        thr = threading.Thread(target=server.run, daemon=True)
        thr.start()
        ok = False
        for __ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.05):
                    ok = True
                    break
            except (ConnectionRefusedError, OSError):
                time.sleep(0.05)

        if ok:
            return server, port
        else:
            if server is not None:
                server.should_exit = True
            thr.join(timeout=1.0)

    raise RuntimeError("uvicorn多次启动失败")


def run_parent_heartbeat(parent_pid: int, shutdown_event: threading.Event):
    # 这个必须要做的兜底防僵尸进程
    while True:
        if (not is_process_alive(parent_pid)) or shutdown_event.is_set():
            break
        time.sleep(2)

# 全局清理任务池
clean_tasks = {}
_clean_task_lock = threading.Lock()

# 以下是api
def create_fastapi_app(valid_token: str, shutdown_event: threading.Event):
    const = Ccore.backend_get_constants()
    cs_1 = FastAPI(title="CleanSlate Backend", version=const["version_num"])
    event_box = [shutdown_event]
    appstate = Ccore.backend_get_appstate()

    def token_auth(authorization: str = Header("")):
        # 管理员服务，token鉴权不可移除，防范本地提权
        if authorization != f"Bearer {valid_token}":
            raise HTTPException(status_code=401, detail="token无效")
        return True

    @cs_1.get("/health")
    def health():
        return {"status": "ok"}

    @cs_1.post("/scan", dependencies=[Depends(token_auth)])
    def api_scan_submit():
        task_id = Ccore.create_scan_task()
        def progress_cb(pct: int):
            Ccore.update_scan_task(task_id, progress=pct)

        def thread_entry():
            Ccore.backend_scan_worker(task_id, progress_cb)

        t = threading.Thread(target=thread_entry, daemon=True)
        t.start()
        return {"task_id": task_id}

    @cs_1.get("/scan_task/{task_id}", dependencies=[Depends(token_auth)])
    def api_get_scan_task(task_id: str):
        task = Ccore.get_scan_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return task
    @cs_1.get("/status", dependencies=[Depends(token_auth)])
    def api_status():
        import shutil
        u = shutil.disk_usage("C:")
        return {
            "total_gb": round(u.total / (1024 ** 3), 2),
            "used_gb": round(u.used / (1024 ** 3), 2),
            "free_gb": round(u.free / (1024 ** 3), 2),
            "usage_percent": round(u.used / u.total * 100, 2)
        }

    @cs_1.get("/version", dependencies=[Depends(token_auth)])
    def api_version():
        return Ccore.backend_get_constants()

    @cs_1.post("/clean", dependencies=[Depends(token_auth)])
    def api_clean(req: dict):
        ids = req.get("ids", [])
        if not ids:
            raise HTTPException(status_code=400, detail="未提供清理项")

        task_id = str(uuid.uuid4())
        q = queue.Queue()
        set_task_event_queue(q)

        with _clean_task_lock:
            clean_tasks[task_id] = {
                "queue": q,
                "events": [],
                "status": "running"
            }

        def worker():
            normal_ids = []
            serial_ids = []
            for tid in ids:
                if tid in SERIAL_TASK_IDS:
                    serial_ids.append(tid)
                else:
                    normal_ids.append(tid)

            if normal_ids:
                run_cleaner_batch_async(normal_ids)
                while True:
                    try:
                        ev = q.get(timeout=1.0)
                    except queue.Empty:
                        continue
                    with _clean_task_lock:
                        clean_tasks[task_id]["events"].append(ev)
                    if ev["type"] == "all_done":
                        break

            for sid in serial_ids:
                with _clean_task_lock:
                    clean_tasks[task_id]["events"].append({"type": "start", "tid": sid, "data": {}})

                res = run_cleaner(sid)

                with _clean_task_lock:
                    clean_tasks[task_id]["events"].append({"type": "finish", "tid": sid, "data": res})

            with _clean_task_lock:
                clean_tasks[task_id]["status"] = "done"

        threading.Thread(target=worker, daemon=True).start()
        return {"task_id": task_id}

    @cs_1.get("/clean_task/{task_id}", dependencies=[Depends(token_auth)])
    def api_get_clean_task(task_id: str):
        with _clean_task_lock:
            if task_id not in clean_tasks:
                raise HTTPException(status_code=404, detail="task not found")
            task = clean_tasks[task_id]
            current_events = task["events"]
            task["events"] = []

        return {
            "status": task["status"],
            "events": current_events
        }

    @cs_1.get("/config", dependencies=[Depends(token_auth)])
    def api_get_config():
        from core import config as cfgmod
        return cfgmod.CONFIG

    @cs_1.post("/config", dependencies=[Depends(token_auth)])
    def api_set_config(req: dict):
        from core import config as cfgmod
        import yaml
        from pathlib import Path

        allowed_top = {
            "check_update", "custom_cache_dirs", "recycle_bin", "scanner",
            "backup", "aggressive_mode_enabled", "enable_patch"
        }

        new_cfg = dict(cfgmod.CONFIG)
        for key in allowed_top:
            if key in req:
                new_cfg[key] = req[key]

        backup = new_cfg.get("backup", {})
        if isinstance(backup, dict):
            d = backup.get("dir", "")
            if d:
                try:
                    Path(d).parent.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    raise HTTPException(status_code=400, detail=f"备份目录无效: {e}")

        for p in new_cfg.get("custom_cache_dirs", []):
            if p and not Path(p).exists():
                raise HTTPException(status_code=400, detail=f"自定义缓存目录不存在: {p}")

        try:
            with open(cfgmod.CONFIG_FILE, "w", encoding="utf-8") as f:
                yaml.safe_dump(new_cfg, f, allow_unicode=True, sort_keys=False)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"写入配置失败: {e}")

        return {"status": "ok", "restart_required": True}

    @cs_1.get("/config/export", dependencies=[Depends(token_auth)])
    def api_export_config():
        from core import config as cfgmod
        try:
            with open(cfgmod.CONFIG_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            return {"status": "ok", "content": content}
        except FileNotFoundError:
            return {"status": "ok", "content": ""}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"读取配置失败: {e}")

    @cs_1.post("/config/import", dependencies=[Depends(token_auth)])
    def api_import_config(req: dict):
        from core import config as cfgmod
        import yaml
        import shutil
        from datetime import datetime

        content = req.get("content", "")
        if not content or not content.strip():
            raise HTTPException(status_code=400, detail="配置内容为空")

        try:
            parsed = yaml.safe_load(content)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"YAML 解析失败: {e}")

        if not isinstance(parsed, dict):
            raise HTTPException(status_code=400, detail="配置内容必须是 YAML 映射（键值对）")

        allowed_top = {
            "check_update", "custom_cache_dirs", "recycle_bin", "scanner",
            "backup", "aggressive_mode_enabled", "enable_patch", "patch_dir"
        }
        unknown = set(parsed.keys()) - allowed_top
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"包含未知字段: {', '.join(sorted(unknown))}")

        backup_path = ""
        if cfgmod.CONFIG_FILE.exists():
            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                bak = cfgmod.CONFIG_FILE.with_name(
                    cfgmod.CONFIG_FILE.name + f".bak_{ts}")
                shutil.copy2(cfgmod.CONFIG_FILE, bak)
                backup_path = str(bak)
            except Exception:
                pass

        try:
            with open(cfgmod.CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"写入配置失败: {e}")

        return {
            "status": "ok",
            "restart_required": True,
            "backup": backup_path
        }
    @cs_1.get("/patches", dependencies=[Depends(token_auth)])
    def api_get_patches():
        return Ccore.backend_get_patch_info()

    @cs_1.post("/patches/import", dependencies=[Depends(token_auth)])
    def api_import_patch(req: dict):
        import base64
        from pathlib import Path
        from core.config import PATCH_DIR

        filename = req.get("filename", "")
        content_b64 = req.get("content_b64", "")

        if not filename:
            raise HTTPException(status_code=400, detail="缺少文件名")
        if not content_b64:
            raise HTTPException(status_code=400, detail="缺少文件内容")

        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.lower()
        if suffix not in ('.bcs', '.py'):
            raise HTTPException(status_code=400, detail="只支持 .bcs 或 .py 补丁文件")

        try:
            content = base64.b64decode(content_b64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"base64 解码失败: {e}")

        PATCH_DIR.mkdir(parents=True, exist_ok=True)
        dest = PATCH_DIR / safe_name
        try:
            dest.write_bytes(content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"写入失败: {e}")

        return {"status": "ok", "saved_to": str(dest), "restart_required": True}

    @cs_1.post("/patches/delete", dependencies=[Depends(token_auth)])
    def api_delete_patch(req: dict):
        from pathlib import Path
        from core.config import PATCH_DIR

        filename = req.get("filename", "")
        if not filename:
            raise HTTPException(status_code=400, detail="缺少文件名")

        safe_name = Path(filename).name
        target = PATCH_DIR / safe_name
        if not target.exists():
            raise HTTPException(status_code=404, detail="文件不存在")

        try:
            target.unlink()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除失败: {e}")

        return {"status": "ok", "restart_required": True}
    @cs_1.post("/shutdown", dependencies=[Depends(token_auth)])
    # 即优雅又简单
    def shutdown():
        event_box[0].set()
        return {"status": "shutting_down", "msg": "Backend开始执行优雅退出"}
    return cs_1

def run_api_mode(pipe_name: str, parent_pid: int):
    pipe_h = 0
    server = None
    const = Ccore.backend_get_constants()
    shutdown_event = threading.Event()
    try:
        pipe_h = pipe_open(pipe_name)

        def _log_handler(log_dict: dict):
            pipe_write_line(pipe_h, log_dict)

        set_backend_log_callback(_log_handler)
        pipe_write_line(pipe_h, {"level": "info", "msg": f"Backend初始化开始 {const['version_num']}"})
        Ccore.initialization()
        pipe_write_line(pipe_h, {"level": "info", "msg": f"扫描完成，应急模式={const['emergency_mode']}"})
        token = secrets.token_urlsafe(32)
        app = create_fastapi_app(token, shutdown_event)
        server, port = start_uvicorn(app)
        # 握手包必须第一行输出,c#好拿
        pipe_write_line(pipe_h, {
            "status": "ok",
            "port": port,
            "token": token,
            "version": const["version_num"]
        })
        run_parent_heartbeat(parent_pid, shutdown_event)
        pipe_write_line(pipe_h, {"level": "warn", "msg": "父进程已退出，Backend准备退出"})
    except Exception as e:
        print(f"[EXCEPTION] run_api_mode捕获异常: {e}")
        import traceback
        traceback.print_exc()
        if pipe_h != 0:
            pipe_write_line(pipe_h, {"level": "error", "msg": str(e)})
    finally:
        set_backend_log_callback(None)
        # 必须释放资源
        if server is not None:
            server.should_exit = True
        pipe_close(pipe_h)

def main_entry():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--pipe", type=str, default="")
    parser.add_argument("--parent-pid", type=int, default=0)
    args = parser.parse_args()
    if args.server:
        print("--server 标记识别成功，准备启动管道服务")
        if not args.pipe or args.parent_pid <= 0:
            print("--server 需要 --pipe 和 --parent-pid")
            sys.exit(1)
        try:
            from core import config
            config.CONFIG = config.load_config()
            print(f"[INIT] BASE_DIR={config.BASE_DIR}")
            print("[INIT] 配置加载完成")
            run_api_mode(args.pipe, args.parent_pid)
            print('api ok ')
        except Exception as e:
            print(f"run_api_mode 异常: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("--server 未识别，直接退出")
        return

if __name__ == "__main__":
    main_entry()
