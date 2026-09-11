import subprocess
import re
import os
import hashlib
import time
from pathlib import Path
from typing import Dict

from config import (
    PATH_TEMP_SYSTEM, PATH_TEMP_USER, PATH_PREFETCH,
    PATH_UPDATE_CACHE, PATH_QQ, PATH_WECHAT_CANDIDATES,
    PATH_HIBERNATION, PATH_CHROME_CACHE, PATH_EDGE_CACHE,
    PATH_FIREFOX_CACHE, PATH_VSCODE_CACHE, PATH_PYCHARM_CACHE,
    PATH_INTELLIJ_CACHE, PATH_SYSTEM_LOGS, PATH_INSTALLER_CACHE,
    PATH_PIP_CACHE, PATH_NPM_CACHE, PATH_YARN_CACHE,
    PATH_MAVEN_REPO, PATH_GRADLE_CACHE, PATH_CONDA_PKGS,
    PATH_JDK_INSTALLS, SCAN_ITEMS, USER_HOME, SYSTEM_DRIVE
)

def _run_cmd(cmd: str) -> str:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return r.stdout + r.stderr
    except Exception:
        return ""

def _get_size_gb(size_bytes: int) -> float:
    return round(size_bytes / (1024 ** 3), 2)

def _parse_gb_from_output(output: str, pattern: str) -> float:
    m = re.search(pattern, output)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return 0.0
    return 0.0

def _get_folder_size(path: Path, max_depth: int = 3) -> int:
    if not path.exists():
        return 0
    total = 0
    def walk_dir(p, depth):
        nonlocal total
        if depth > max_depth:
            return
        try:
            for item in p.iterdir():
                if item.is_file():
                    try:
                        total += item.stat().st_size
                    except (OSError, PermissionError):
                        pass
                elif item.is_dir():
                    walk_dir(item, depth + 1)
        except (OSError, PermissionError):
            pass
    walk_dir(path, 0)
    return total

def scan_shadow_storage() -> Dict:
    out = _run_cmd("vssadmin list shadowstorage")
    size = _parse_gb_from_output(out, r"已用卷影副本存储空间:\s*([\d.]+)\s*GB")
    return {
        "size_gb": size,
        "can_clean": size > 0.1,
        "detail": f"系统还原点，占用 {size:.2f} GB"
    }

def scan_winsxs() -> Dict:
    out = _run_cmd("Dism /Online /Cleanup-Image /AnalyzeComponentStore")
    if "推荐使用组件存储清理 : 是" not in out:
        return {"size_gb": 0.0, "can_clean": False, "detail": "WinSxS 无需清理"}
    m = re.search(r"可回收的组件存储空间\s*:\s*([\d.]+)\s*MB", out)
    if not m:
        m = re.search(r"组件存储的实际大小\s*:\s*([\d.]+)\s*MB", out)
    if m:
        gb = round(float(m.group(1)) / 1024, 2)
        return {"size_gb": gb, "can_clean": True, "detail": f"WinSxS 可清理 {gb:.2f} GB（清理后将无法卸载 Windows 更新）"}
    return {"size_gb": 0.0, "can_clean": False, "detail": "WinSxS 状态未知"}

def scan_temp_system() -> Dict:
    p = PATH_TEMP_SYSTEM
    if not p.exists():
        return {"size_gb": 0.0, "can_clean": False, "detail": "系统临时文件夹不存在"}
    gb = _get_size_gb(_get_folder_size(p))
    return {"size_gb": gb, "can_clean": gb > 0.01, "detail": f"系统临时文件 {gb:.2f} GB"}

def scan_temp_user() -> Dict:
    p = PATH_TEMP_USER
    if not p.exists():
        return {"size_gb": 0.0, "can_clean": False, "detail": "用户临时文件夹不存在"}
    gb = _get_size_gb(_get_folder_size(p))
    return {"size_gb": gb, "can_clean": gb > 0.01, "detail": f"用户临时文件 {gb:.2f} GB"}

def scan_prefetch() -> Dict:
    p = PATH_PREFETCH
    if not p.exists():
        return {"size_gb": 0.0, "can_clean": False, "detail": "预读文件夹不存在"}
    total = 0
    for f in p.glob('*'):
        if f.is_file():
            try:
                total += f.stat().st_size
            except (OSError, PermissionError):
                pass
    gb = _get_size_gb(total)
    return {"size_gb": gb, "can_clean": gb > 0.01, "detail": f"预读缓存 {gb:.2f} GB"}

def scan_update_cache() -> Dict:
    p = PATH_UPDATE_CACHE
    if not p.exists():
        return {"size_gb": 0.0, "can_clean": False, "detail": "更新缓存文件夹不存在"}
    gb = _get_size_gb(_get_folder_size(p))
    return {"size_gb": gb, "can_clean": gb > 0.01, "detail": f"更新缓存 {gb:.2f} GB"}

def scan_qq_residue() -> Dict:
    p = PATH_QQ
    if not p.exists():
        return {"size_gb": 0.0, "can_clean": False, "detail": "QQ 残留不存在"}
    gb = _get_size_gb(_get_folder_size(p))
    return {"size_gb": gb, "can_clean": gb > 0.01, "detail": f"QQ 残留 {gb:.2f} GB"}

def scan_wechat_cache() -> Dict:
    for cand in PATH_WECHAT_CANDIDATES:
        if cand.exists():
            gb = _get_size_gb(_get_folder_size(cand))
            if gb > 0.1:
                return {
                    "size_gb": gb,
                    "can_clean": False,
                    "detail": f"微信缓存位于 {cand}，占用 {gb:.2f} GB，请在微信设置中手动清理"
                }
    return {"size_gb": 0.0, "can_clean": False, "detail": "未检测到微信缓存"}

def scan_hibernation() -> Dict:
    p = PATH_HIBERNATION
    if p.exists():
        gb = _get_size_gb(p.stat().st_size)
        return {"size_gb": gb, "can_clean": True, "detail": f"休眠文件启用 {gb:.2f} GB（关闭后无法使用休眠功能）"}
    return {"size_gb": 0.0, "can_clean": False, "detail": "休眠已关闭"}

def _get_file_hash_sample(filepath: Path) -> str:
    size = filepath.stat().st_size
    try:
        with open(filepath, 'rb') as f:
            if size > 1024 * 1024:
                sample = f.read(1024 * 1024)
                f.seek(-1024 * 1024, 2)
                sample += f.read(1024 * 1024)
                return hashlib.md5(sample).hexdigest()
            else:
                return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""

def scan_duplicate_files() -> Dict:
    target_dirs = [
        USER_HOME / 'Documents',
        USER_HOME / 'Downloads',
        USER_HOME / 'Desktop',
        USER_HOME / 'Pictures',
        USER_HOME / 'Music',
        USER_HOME / 'Videos',
    ]
    size_map = {}
    count = 0
    print(" 收集文件...", end="", flush=True)
    for base in target_dirs:
        if not base.exists():
            continue
        for f in base.rglob('*'):
            if f.is_file() and f.stat().st_size > 1024:
                count += 1
                if count % 1000 == 0:
                    print(".", end="", flush=True)
                size = f.stat().st_size
                if size not in size_map:
                    size_map[size] = []
                size_map[size].append(f)
    print(" 分组完成", flush=True)
    hashes = {}
    total_dup_size = 0
    print(" 计算哈希...", end="", flush=True)
    hash_count = 0
    for size, files in size_map.items():
        if len(files) < 2:
            continue
        for f in files:
            hash_count += 1
            if hash_count % 100 == 0:
                print(".", end="", flush=True)
            file_hash = _get_file_hash_sample(f)
            if not file_hash:
                continue
            if file_hash in hashes:
                total_dup_size += f.stat().st_size
            else:
                hashes[file_hash] = f
    print(" 完成", flush=True)
    size_gb = _get_size_gb(total_dup_size)
    return {
        "size_gb": size_gb,
        "can_clean": size_gb > 0.01,
        "detail": f"重复文件，可释放 {size_gb:.2f} GB（删除后保留第一个文件）"
    }
"""
def scan_large_files() -> Dict:
    target_dirs = [
        USER_HOME / 'Documents',
        USER_HOME / 'Downloads',
        USER_HOME / 'Desktop',
        USER_HOME / 'Pictures',
        USER_HOME / 'Music',
        USER_HOME / 'Videos',
        Path(f'{SYSTEM_DRIVE}/Program Files'),
        Path(f'{SYSTEM_DRIVE}/Program Files (x86)'),
    ]
    large_files = []
    total_size = 0
    count = 0
    max_files = 10000
    start_time = time.time()
    timeout = 8
    print(" 扫描大文件...", end="", flush=True)

    def scan_dir(path, depth=0, max_depth=2):
        nonlocal count, total_size
        if depth > max_depth:
            return
        if time.time() - start_time > timeout:
            return
        try:
            with os.scandir(path) as it:
                for entry in it:
                    count += 1
                    if count % 500 == 0:
                        print(".", end="", flush=True)
                    if count > max_files:
                        return
                    if time.time() - start_time > timeout:
                        return
                    try:
                        if entry.is_file(follow_symlinks=False):
                            sz = entry.stat().st_size
                            if sz > 1024 ** 3:
                                large_files.append(Path(entry.path))
                                total_size += sz
                        elif entry.is_dir(follow_symlinks=False):
                            scan_dir(Path(entry.path), depth + 1, max_depth)
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass

    for base in target_dirs:
        if not base.exists():
            continue
        scan_dir(base, 0, 2)
        if count > max_files or time.time() - start_time > timeout:
            break

    print(" 完成", flush=True)
    size_gb = _get_size_gb(total_size)
    detail = f"大文件 (>1GB)，共 {len(large_files)} 个，占用 {size_gb:.2f} GB"
    if count >= max_files:
        detail += " (达到扫描上限)"
    if time.time() - start_time > timeout:
        detail += " (扫描超时)"
    return {"size_gb": size_gb, "can_clean": size_gb > 0.01, "detail": detail}
"""
def scan_empty_folders() -> Dict:
    target_dirs = [
        USER_HOME / 'Documents',
        USER_HOME / 'Downloads',
        USER_HOME / 'Desktop',
        USER_HOME / 'Pictures',
        USER_HOME / 'Music',
        USER_HOME / 'Videos',
        Path(f'{SYSTEM_DRIVE}/Users/Public'),
    ]
    empty_count = 0
    for base in target_dirs:
        if not base.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            if not filenames and not dirnames:
                empty_count += 1
    return {"size_gb": 0.0, "can_clean": empty_count > 0, "detail": f"空文件夹 {empty_count} 个"}

def scan_browser_cache() -> Dict:
    total = 0
    cache_dirs = [PATH_CHROME_CACHE, PATH_EDGE_CACHE]
    if PATH_FIREFOX_CACHE.exists():
        for profile in PATH_FIREFOX_CACHE.glob('*.default*'):
            cache_dir = profile / 'cache2'
            if cache_dir.exists():
                cache_dirs.append(cache_dir)
    for p in cache_dirs:
        if p.exists():
            total += _get_folder_size(p)
    size_gb = _get_size_gb(total)
    return {"size_gb": size_gb, "can_clean": size_gb > 0.01, "detail": f"浏览器缓存 {size_gb:.2f} GB"}

def scan_ide_cache() -> Dict:
    total = 0
    if PATH_VSCODE_CACHE.exists():
        total += _get_folder_size(PATH_VSCODE_CACHE)
    for p in PATH_PYCHARM_CACHE.parent.glob('PyCharm*'):
        cache_dir = p / 'cache'
        if cache_dir.exists():
            total += _get_folder_size(cache_dir)
    for p in PATH_INTELLIJ_CACHE.parent.glob('IntelliJIdea*'):
        cache_dir = p / 'cache'
        if cache_dir.exists():
            total += _get_folder_size(cache_dir)
    size_gb = _get_size_gb(total)
    return {"size_gb": size_gb, "can_clean": size_gb > 0.01, "detail": f"IDE 缓存 {size_gb:.2f} GB"}

def scan_log_files() -> Dict:
    p = PATH_SYSTEM_LOGS
    if not p.exists():
        return {"size_gb": 0.0, "can_clean": False, "detail": "系统日志目录不存在"}
    total = 0
    extensions = ('.log', '.etl', '.evtx')
    now = time.time()
    cutoff = now - 30 * 24 * 3600
    for ext in extensions:
        for f in p.rglob(f'*{ext}'):
            if f.is_file():
                try:
                    if f.stat().st_mtime < cutoff:
                        total += f.stat().st_size
                except (OSError, PermissionError):
                    pass
    size_gb = _get_size_gb(total)
    return {"size_gb": size_gb, "can_clean": size_gb > 0.01, "detail": f"日志文件 (超30天) {size_gb:.2f} GB"}

def scan_installer_cache() -> Dict:
    p = PATH_INSTALLER_CACHE
    if not p.exists():
        return {"size_gb": 0.0, "can_clean": False, "detail": "安装包缓存目录不存在"}
    total = _get_folder_size(p)
    size_gb = _get_size_gb(total)
    return {"size_gb": size_gb, "can_clean": size_gb > 0.01, "detail": f"安装包缓存 {size_gb:.2f} GB"}

def scan_pip_cache() -> Dict:
    p = PATH_PIP_CACHE
    if not p.exists():
        return {"size_gb": 0.0, "can_clean": False, "detail": "pip缓存不存在"}
    gb = _get_size_gb(_get_folder_size(p))
    return {"size_gb": gb, "can_clean": gb > 0.01, "detail": f"pip缓存 {gb:.2f} GB"}

def scan_npm_cache() -> Dict:
    p = PATH_NPM_CACHE
    if not p.exists():
        return {"size_gb": 0.0, "can_clean": False, "detail": "npm缓存不存在"}
    gb = _get_size_gb(_get_folder_size(p))
    return {"size_gb": gb, "can_clean": gb > 0.01, "detail": f"npm缓存 {gb:.2f} GB"}

def scan_yarn_cache() -> Dict:
    p = PATH_YARN_CACHE
    if not p.exists():
        return {"size_gb": 0.0, "can_clean": False, "detail": "yarn缓存不存在"}
    gb = _get_size_gb(_get_folder_size(p))
    return {"size_gb": gb, "can_clean": gb > 0.01, "detail": f"yarn缓存 {gb:.2f} GB"}

def scan_maven_repo() -> Dict:
    p = PATH_MAVEN_REPO
    if not p.exists():
        return {"size_gb": 0.0, "can_clean": False, "detail": "Maven仓库不存在"}
    gb = _get_size_gb(_get_folder_size(p))
    return {"size_gb": gb, "can_clean": gb > 0.01, "detail": f"Maven本地仓库 {gb:.2f} GB"}

def scan_gradle_cache() -> Dict:
    p = PATH_GRADLE_CACHE
    if not p.exists():
        return {"size_gb": 0.0, "can_clean": False, "detail": "Gradle缓存不存在"}
    gb = _get_size_gb(_get_folder_size(p))
    return {"size_gb": gb, "can_clean": gb > 0.01, "detail": f"Gradle缓存 {gb:.2f} GB"}

def scan_conda_pkgs() -> Dict:
    p = PATH_CONDA_PKGS
    if not p.exists():
        return {"size_gb": 0.0, "can_clean": False, "detail": "Conda包缓存不存在"}
    gb = _get_size_gb(_get_folder_size(p))
    return {"size_gb": gb, "can_clean": gb > 0.01, "detail": f"Conda包缓存 {gb:.2f} GB"}

def scan_jdk_versions() -> Dict:
    java_paths = []
    search_dirs = [
        Path(f'{SYSTEM_DRIVE}/Program Files/Java'),
        Path(f'{SYSTEM_DRIVE}/Program Files (x86)/Java'),
        USER_HOME / 'AppData/Local/Java',
        USER_HOME / 'AppData/Roaming/Java',
        USER_HOME / '.sdkman/candidates/java',
        USER_HOME / 'jdk',
        Path(f'{SYSTEM_DRIVE}/jdk'),
    ]
    try:
        result = subprocess.run(
            'where java 2>nul',
            shell=True,
            capture_output=True,
            text=True
        )
        for line in result.stdout.splitlines():
            p = Path(line.strip())
            if p.exists() and p.name.lower() == 'java.exe':
                jdk_root = p.parent.parent
                if jdk_root not in java_paths:
                    java_paths.append(jdk_root)
    except Exception:
        pass
    if not java_paths:
        for base in search_dirs:
            if not base.exists():
                continue
            for item in base.glob('*'):
                if item.is_dir():
                    java_exe = item / 'bin' / 'java.exe'
                    if java_exe.exists():
                        java_paths.append(item)
    if not java_paths:
        return {"size_gb": 0.0, "can_clean": False, "detail": "未发现 JDK 安装"}
    total_size = 0
    for p in java_paths:
        total_size += _get_folder_size(p)
    gb = _get_size_gb(total_size)
    detail = f"发现 {len(java_paths)} 个 JDK 安装，总占用 {gb:.2f} GB"
    if len(java_paths) > 1:
        detail += f"，建议保留最新版本"
    return {
        "size_gb": gb,
        "can_clean": len(java_paths) > 1,
        "detail": detail
    }

def scan_thumbnails() -> Dict:
    p = USER_HOME / 'AppData/Local/Microsoft/Windows/Explorer'
    total = 0
    if p.exists():
        for f in p.glob('thumbcache_*.db'):
            try:
                total += f.stat().st_size
            except (OSError, PermissionError):
                pass
    size_gb = _get_size_gb(total)
    return {"size_gb": size_gb, "can_clean": size_gb > 0.01, "detail": f"缩略图缓存 {size_gb:.2f} GB"}

def scan_error_reports() -> Dict:
    paths = [
        USER_HOME / 'AppData/Local/Microsoft/Windows/WER',
        Path(f'{SYSTEM_DRIVE}/ProgramData/Microsoft/Windows/WER'),
    ]
    total = 0
    for p in paths:
        if p.exists():
            total += _get_folder_size(p, max_depth=2)
    size_gb = _get_size_gb(total)
    return {"size_gb": size_gb, "can_clean": size_gb > 0.01, "detail": f"错误报告 {size_gb:.2f} GB"}

def scan_delivery_opt() -> Dict:
    p = Path(f'{SYSTEM_DRIVE}/Windows/SoftwareDistribution/DeliveryOptimization')
    total = 0
    if p.exists():
        total = _get_folder_size(p, max_depth=3)
    size_gb = _get_size_gb(total)
    return {"size_gb": size_gb, "can_clean": size_gb > 0.01, "detail": f"传递优化 {size_gb:.2f} GB"}

SCAN_MAP = {
    'shadow': scan_shadow_storage,
    'winsxs': scan_winsxs,
    'temp_sys': scan_temp_system,
    'temp_user': scan_temp_user,
    'prefetch': scan_prefetch,
    'update_cache': scan_update_cache,
    'qq_residue': scan_qq_residue,
    'wechat_cache': scan_wechat_cache,
    'hibernation': scan_hibernation,
    'duplicate_files': scan_duplicate_files,
    #'large_files': scan_large_files,
    'empty_folders': scan_empty_folders,
    'browser_cache': scan_browser_cache,
    'ide_cache': scan_ide_cache,
    'log_files': scan_log_files,
    'installer_cache': scan_installer_cache,
    'pip_cache': scan_pip_cache,
    'npm_cache': scan_npm_cache,
    'yarn_cache': scan_yarn_cache,
    'maven_repo': scan_maven_repo,
    'gradle_cache': scan_gradle_cache,
    'conda_pkgs': scan_conda_pkgs,
    'jdk_versions': scan_jdk_versions,
    'thumbnails': scan_thumbnails,
    'error_reports': scan_error_reports,
    'delivery_opt': scan_delivery_opt,
}

def get_all_scans() -> Dict[str, Dict]:
    results = {}
    for item in SCAN_ITEMS:
        func = SCAN_MAP.get(item['id'])
        if func:
            print(f"正在扫描: {item['name']}...", end="", flush=True)
            data = func()
            data['risk'] = item['risk']
            results[item['id']] = data
            print(f" 完成 ({data.get('size_gb',0):.2f} GB)")
    return results

from config import CUSTOM_CACHE_DIRS, ENABLE_RECYCLE_BIN

def scan_recycle_bin() -> Dict:
    try:
        total = 0
        recycle_path = Path('C:/$Recycle.bin')
        if recycle_path.exists():
            total = _get_folder_size(recycle_path)
        size_gb = _get_size_gb(total)
        return {"size_gb": size_gb, "can_clean": size_gb > 0.01, "detail": f"回收站 {size_gb:.2f} GB"}
    except Exception:
        return {"size_gb": 0.0, "can_clean": False, "detail": "回收站扫描失败"}

def scan_custom_cache(path: Path) -> Dict:
    if not path.exists():
        return {"size_gb": 0.0, "can_clean": False, "detail": f"自定义目录不存在: {path}"}
    gb = _get_size_gb(_get_folder_size(path))
    return {"size_gb": gb, "can_clean": gb > 0.01, "detail": f"自定义缓存 {path.name} {gb:.2f} GB"}

if ENABLE_RECYCLE_BIN:
    SCAN_MAP['recycle_bin'] = scan_recycle_bin

for idx, p in enumerate(CUSTOM_CACHE_DIRS):
    if p.exists():
        SCAN_MAP[f'custom_{idx}'] = lambda p=p: scan_custom_cache(p)