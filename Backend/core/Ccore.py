import sys
import shutil
import importlib.util
import time
import struct
import threading
from operator import truediv
from core.logutil import backend_log, set_backend_log_callback
from pathlib import Path
from core.scanner import get_all_scans
from core.cleaner import run_cleaner, CLEAN_MAP
from core.config import AGGRESSIVE_MODE_ENABLED, ENABLE_PATCH, PATCH_DIR, BACKUP_DIR, BACKUP_RETENTION_DAYS, EMERGENCY_MODE, BASE_DIR, CHECK_UPDATE

class AppState:
    data = {}



VERSION_NUM = "正式版v1.0.4"  #别忘了改这个！！！！！！！！！！！！！！！！！！
VERSION_CODE = 1004   #别忘了改这个！！！！！！！！！！！！！！！！！！
TEMP_PATCH_DIR = BASE_DIR / 'temp_patches'
PATCH_RETENTION_DAYS = 30
_patch_scans = []
_patch_ids = set()


from typing import Callable, Dict, Any

scan_task_pool: Dict[str, Dict[str, Any]] = {}
_scan_task_lock = threading.Lock()

def create_scan_task() -> str:
    import uuid
    tid = str(uuid.uuid4())
    with _scan_task_lock:
        scan_task_pool[tid] = {
            "status": "pending",   # pending / running / done / error
            "progress": 0,        # 0‑100
            "result": None,
            "error": None
        }
    return tid

def update_scan_task(task_id: str, **kwargs):
    with _scan_task_lock:
        if task_id not in scan_task_pool:
            return
        t = scan_task_pool[task_id]
        for k,v in kwargs.items():
            if k in t:
                t[k] = v

def get_scan_task(task_id: str):
    with _scan_task_lock:
        if task_id not in scan_task_pool:
            return None
        return scan_task_pool[task_id].copy()


def get_disk_info():
    try:
        usage = shutil.disk_usage('C:')
        total_gb = usage.total / (1024**3)
        free_gb = usage.free / (1024**3)
        used_gb = usage.used / (1024**3)
        return total_gb, free_gb, used_gb
    except Exception:
        return "无法获取磁盘信息"

def display_results(data):
    print("\n" + "=" * 70)
    print("扫描结果")
    print("=" * 70)
    print(f"{'序号':<6} {'项':<20} {'大小(GB)':<10} {'风险':<8} 说明")
    print("-" * 70)
    total = 0
    id_map = {}
    idx = 1
    for item_id, info in data.items():
        size = info.get('size_gb', 0)
        total += size
        risk = info.get('risk', 'low')
        risk_cn = {'low': '低', 'medium': '中', 'high': '高'}.get(risk, '低')
        detail = info.get('detail', '')[:40]
        print(f"{idx:<6} {info.get('name', item_id):<20} {size:<10.2f} {risk_cn:<8} {detail}")
        id_map[idx] = item_id
        idx += 1
    print("-" * 70)
    print(f"总计可释放: {total:.2f} GB")
    print("=" * 70)
    print("风险等级: 低=安全可删  中=建议保留最近  高=需谨慎确认")
    print("=" * 70)
    return id_map

def show_clean_result(success_count, fail_count, total_freed_gb):
    print("\n" + "-" * 70)
    print(f"清理完成: 成功 {success_count} 项, 失败 {fail_count} 项")
    print(f"总计释放: {total_freed_gb:.2f} GB")
    print("-" * 70)

def progress_disk(total_gb, used_gb):
    try:
        progress_str = "占用：["
        total_gb = round(total_gb, 2)
        used_gb = round(used_gb, 2)
        progress = round(used_gb/total_gb, 2)*20
        for x in range(0, 20):
            if x >= progress:
                progress_str += " "
            else:
                progress_str += "/"
        progress_str += "]"
        progress = str(progress*5)+"%"
    except Exception:
        progress, progress_str = "", ""
    return progress_str, progress

def clean_old_files(directory, days, pattern="*", description=""):
    if not directory.exists():
        return 0
    now = time.time()
    cutoff = now - (days * 24 * 3600)
    deleted = 0
    for f in directory.glob(pattern):
        if f.is_file():
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    deleted += 1
            except Exception:
                pass
    if deleted > 0 and description:
        print(f"[清理] 已删除 {deleted} 个超过 {days} 天的{description}")
    return deleted

def clean_backup_files():
    return clean_old_files(BACKUP_DIR, BACKUP_RETENTION_DAYS, "*.zip", "备份文件")

def clean_temp_patches():
    return clean_old_files(TEMP_PATCH_DIR, PATCH_RETENTION_DAYS, "*", "临时补丁文件")
import hashlib
def load_patch_file(filepath):
    filepath = Path(filepath)
    if filepath.suffix.lower() == '.bcs':
        try:
            with open(filepath, 'rb') as f:
                magic = f.read(4)
                if magic != b'CLSL':
                    print("[补丁] 不是有效的 bcs 文件 (魔数不匹配)")
                    return None
                version = struct.unpack('B', f.read(1))[0]
                if version != 2:
                    print(f"[补丁] 不支持的版本: {version}，请使用最新版打包工具重新打包")
                    return None
                time_bytes = f.read(19)
                if len(time_bytes) != 19:
                    print("[补丁] 时间字段长度错误")
                    return None
                try:
                    pack_time = time_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    pack_time = "未知时间"
                author_bytes = b''
                while True:
                    c = f.read(1)
                    if c == b'\x00' or not c:
                        break
                    author_bytes += c
                author = author_bytes.decode('utf-8') if author_bytes else "未知作者"
                stored_hash = f.read(64).decode('utf-8')
                if len(stored_hash) != 64:
                    print("[补丁] SHA256 长度错误")
                    return None
                py_len = struct.unpack('<I', f.read(4))[0]
                if py_len <= 0:
                    print("[补丁] Python 长度无效")
                    return None
                yaml_len = struct.unpack('<I', f.read(4))[0]
                py_data = f.read(py_len)
                yaml_data = f.read(yaml_len)
                if len(py_data) != py_len:
                    print(f"[补丁] Python 数据不完整 (预期 {py_len}, 实际 {len(py_data)})")
                    return None
                calc_hash = hashlib.sha256(py_data + yaml_data).hexdigest()
                if calc_hash != stored_hash:
                    print("[补丁] SHA256 校验失败，文件可能损坏")
                    return None
            TEMP_PATCH_DIR.mkdir(parents=True, exist_ok=True)
            py_path = TEMP_PATCH_DIR / f"{filepath.stem}.py"
            yaml_path = TEMP_PATCH_DIR / f"{filepath.stem}.yaml"
            py_path.write_bytes(py_data)
            yaml_path.write_bytes(yaml_data)
            print(f"[补丁] 解包完成: {py_path.name} (作者: {author}, 时间: {pack_time})")
            print(f"[补丁] SHA256 校验通过")
            filepath = py_path
        except Exception as e:
            print(f"[补丁] 解包失败: {e}")
            return None
    if filepath.suffix.lower() != '.py':
        print("[补丁] 不支持的文件类型，请加载 .py 或 .bcs 文件")
        return None
    try:
        spec = importlib.util.spec_from_file_location("patch_module", filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if hasattr(module, 'execute_once'):
            print("[补丁] 检测到临时补丁，立即执行...")
            result = module.execute_once()
            if result:
                print("临时补丁执行完成:")
                for k, v in result.items():
                    print(f"  {k}: {v}")
            else:
                print("临时补丁执行失败或未返回结果")
            return None
        if hasattr(module, 'register_patch'):
            patch_info = module.register_patch()
            if not isinstance(patch_info, dict):
                print("[补丁] register_patch 必须返回字典")
                return None
            required_keys = ['id', 'name', 'scan', 'clean']
            for k in required_keys:
                if k not in patch_info:
                    print(f"[补丁] 缺少必需键: {k}")
                    return None
            return patch_info
        print("[补丁] 补丁文件缺少 register_patch 或 execute_once 函数")
        return None
    except Exception as e:
        print(f"[补丁] 加载失败: {e}")
        return None

def load_patches_from_dir():
    if not PATCH_DIR.exists():
        PATCH_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[补丁] 补丁目录已自动创建: {PATCH_DIR}")
        return
    print(f"[补丁] 扫描补丁目录: {PATCH_DIR}")
    loaded = 0
    patch_files = []
    for ext in ['.bcs', '.py']:
        for f in PATCH_DIR.glob(f'*{ext}'):
            if f.is_file():
                patch_files.append(f)
    if not patch_files:
        print("[补丁] 目录中没有补丁文件")
        return
    for f in patch_files:
        patch_info = load_patch_file(str(f))
        if patch_info is None:
            continue
        pid = patch_info['id']
        if pid in _patch_ids:
            print(f"[补丁] {pid} 已加载，跳过")
            continue
        CLEAN_MAP[pid] = patch_info['clean']
        _patch_scans.append(patch_info['scan'])
        _patch_ids.add(pid)
        try:
            result = patch_info['scan']()
            if result:
                AppState.data[pid] = result
        except Exception as e:
            print(f"[补丁] {pid} 初始扫描失败: {e}")
        print(f"[补丁] 加载成功: {patch_info['name']} ({pid})")
        loaded += 1
    if loaded > 0:
        print(f"[补丁] 共加载 {loaded} 个补丁")

def spinner(text):
    #!!!用这个一定要执行stop函数，要不然进程停不下来!!!
    #不能用于有日志输出的函数
    #不确定去283-285行看
    stop_flag = [True]
    def _spinner_inner():
        symbols = ['|', '/', '-', '\\']
        idx = 0
        while stop_flag[0]:
            s = symbols[idx % len(symbols)]
            print(f"\r{text} {s}", end="", flush=True)
            idx += 1
            time.sleep(0.20)
    th = threading.Thread(target=_spinner_inner, daemon=True)
    th.start()
    def stop():
        stop_flag[0] = False
        th.join()
        print("\r" + " "*50 + "\r", end="", flush=True)
    return stop
def New_Version():
    import json
    from urllib.request import urlopen
    from urllib.error import URLError
    url_list = [
        "https://raw.giteeusercontent.com/nuln-studio/CleanSlate/raw/master/latest_version.json",
        "https://raw.githubusercontent.com/Nuln-Studio/CleanSlate/master/latest_version.json"
    ]
    remote_data = None
    for url in url_list:
        try:
            resp = urlopen(url, timeout=6)
            remote_data = json.loads(resp.read())
            break
        except (URLError, Exception):
            continue
    if remote_data is None:
        print("\n获取版本信息失败,跳过自动更新")
    elif remote_data["version_code"] > VERSION_CODE:
        print(f"\n发现新版本：{remote_data['latest_version']}")
        print(f"更新说明：{remote_data['note']}")
        print(f"发行版地址：{remote_data['github_release_url']}")
    else:
        print("\n未发现新版本")

def backend_scan_worker(task_id: str, progress_callback: Callable[[int], None]):
    """
    子线程执行的扫描工作函数
    progress_callback(percent): 上报进度 0~100
    """
    try:
        update_scan_task(task_id, status="running", progress=0)
        progress_callback(5)
        get_disk_info()

        progress_callback(20)
        AppState.data = get_all_scans()

        progress_callback(50)
        load_patches_from_dir()

        progress_callback(75)
        for func in _patch_scans:
            try:
                res = func()
                if res:
                    AppState.data[res.get("id")] = res
            except Exception:
                pass

        progress_callback(100)
        update_scan_task(task_id, status="done", progress=100, result=list(AppState.data.values()))
    except Exception as e:
        import traceback
        err_txt = traceback.format_exc()
        update_scan_task(task_id, status="error", error=err_txt)

def backend_scan():
    get_disk_info()
    AppState.data = get_all_scans()
    load_patches_from_dir()
    for func in _patch_scans:
        try:
            res = func()
            if res:
                AppState.data[res.get("id")] = res
        except Exception:
            pass


def backend_get_appstate():
    return AppState

def backend_get_constants():
    return {
        "version_num": VERSION_NUM,
        "version_code": VERSION_CODE,
        "emergency_mode": EMERGENCY_MODE
    }
def initialization(): #初始化清缓存
    get_disk_info()
    clean_backup_files()
    clean_temp_patches()
    return True
