import sys
import socket
import secrets
import threading
import time
import json
import ctypes
from ctypes import wintypes
from core.logutil import set_backend_log_callback
from fastapi import FastAPI, Depends, Header, HTTPException
import uvicorn
from core import Ccore
from core.cleaner import run_cleaner

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

def find_free_port(start: int = 72916) -> int:  #72916幸运数字不要改！！！
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

# 以下是api
def create_fastapi_app(valid_token: str,shutdown_event: threading.Event):
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
        # allow_high_risk保留，原本的高风险确认用GUI
        allow_high_risk = req.get("allow_high_risk", False)
        total_success = total_failed = total_freed_gb = 0
        details = []
        for item_id in ids:
            res = run_cleaner(item_id)
            if res["success"]:
                total_success += 1
            else:
                total_failed += 1
            total_freed_gb += res.get("freed_gb", 0.0)
            details.append({
                "id": item_id,
                "success": res["success"],
                "freed_gb": res.get("freed_gb", 0.0),
                "message": res["message"]
            })
        return {
            "total_success": total_success,
            "total_failed": total_failed,
            "total_freed_gb": round(total_freed_gb, 2),
            "details": details
        }

    @cs_1.post("/shutdown", dependencies=[Depends(token_auth)])
    #即优雅又简单
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
