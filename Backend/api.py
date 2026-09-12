import sys
import socket
import secrets
import threading
import time
import json
import ctypes
from ctypes import wintypes

from fastapi import FastAPI, Depends, Header, HTTPException
import uvicorn

import main
from cleaner import run_cleaner


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
    for port in range(start, 65535):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("无可用本地回环端口")


def start_uvicorn(app):
    # uvicorn会阻塞，必须后台线程；禁止放到主线程运行
    for _ in range(8):
        port = find_free_port()
        cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_config=None)
        server = uvicorn.Server(cfg)
        thr = threading.Thread(target=server.run, daemon=True)
        thr.start()
        for __ in range(100):
            if server.started:
                return server, port
            if not thr.is_alive():
                time.sleep(0.05)
                break
    raise RuntimeError("uvicorn多次启动失败")


def run_parent_heartbeat(parent_pid: int):
    # 占用主线程做心跳监控
    # 这个必须要做的兜底防僵尸进程
    while True:
        if not is_process_alive(parent_pid):
            break
        time.sleep(2)

# 以下是api
def create_fastapi_app(valid_token: str):
    const = main.backend_get_constants()
    cs_1 = FastAPI(title="CleanSlate Backend", version=const["version_num"])
    appstate = main.backend_get_appstate()

    def token_auth(authorization: str = Header("")):
        # 管理员服务，token鉴权不可移除，防范本地提权
        if authorization != f"Bearer {valid_token}":
            raise HTTPException(status_code=401, detail="token无效")
        return True

    @cs_1.get("/health")
    def health():
        return {"status": "ok"}

    @cs_1.post("/scan", dependencies=[Depends(token_auth)])
    def api_scan():
        main.backend_scan()
        return {"status": "ok", "items": list(appstate.data.values())}

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
        return main.backend_get_constants()

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
        import os
        os._exit(0)
    return cs_1


def run_api_mode(pipe_name: str, parent_pid: int):
    pipe_h = 0
    server = None
    const = main.backend_get_constants()
    try:
        pipe_h = pipe_open(pipe_name)
        pipe_write_line(pipe_h, {"level": "info", "msg": f"Backend初始化开始 {const['version_num']}"})

        main.initialization()
        pipe_write_line(pipe_h, {"level": "info", "msg": f"扫描完成，应急模式={const['emergency_mode']}"})

        token = secrets.token_urlsafe(32)
        app = create_fastapi_app(token)
        server, port = start_uvicorn(app)

        # 握手包必须第一行输出,c#好拿
        pipe_write_line(pipe_h, {
            "status": "ok",
            "port": port,
            "token": token,
            "version": const["version_num"]
        })

        run_parent_heartbeat(parent_pid)
        pipe_write_line(pipe_h, {"level": "warn", "msg": "父进程已退出，Backend准备退出"})

    except Exception as e:
        if pipe_h != 0:
            pipe_write_line(pipe_h, {"level": "error", "msg": str(e)})
    finally:
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
        if not args.pipe or args.parent_pid <= 0:
            print("--server 需要 --pipe 和 --parent-pid")
            sys.exit(1)
        run_api_mode(args.pipe, args.parent_pid)



if __name__ == "__main__":
    main_entry()
