import subprocess
import shutil
import hashlib
import os
import time
import re
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Dict
from datetime import datetime

from config import (
    PATH_TEMP_SYSTEM, PATH_TEMP_USER, PATH_PREFETCH,
    PATH_UPDATE_CACHE, PATH_QQ, PATH_HIBERNATION,
    PATH_CHROME_CACHE, PATH_EDGE_CACHE, PATH_FIREFOX_CACHE,
    PATH_VSCODE_CACHE, PATH_PYCHARM_CACHE, PATH_INTELLIJ_CACHE,
    PATH_SYSTEM_LOGS, PATH_INSTALLER_CACHE,
    PATH_PIP_CACHE, PATH_NPM_CACHE, PATH_YARN_CACHE,
    PATH_MAVEN_REPO, PATH_GRADLE_CACHE, PATH_CONDA_PKGS,
    PATH_JDK_INSTALLS,
    CUSTOM_CACHE_DIRS,
    RECYCLE_BIN_ENABLED,
    BACKUP_ENABLED,
    BACKUP_DIR,
    USER_HOME,
    SYSTEM_DRIVE,
    EMERGENCY_MODE
)

RISK_MAP = {
    'shadow': 'medium',
    'winsxs': 'high',
    'temp_sys': 'low',
    'temp_user': 'low',
    'prefetch': 'low',
    'update_cache': 'low',
    'qq_residue': 'low',
    'wechat_cache': 'low',
    'hibernation': 'low',
    'duplicate_files': 'medium',
    #'large_files': 'high',
    'empty_folders': 'low',
    'browser_cache': 'low',
    'ide_cache': 'low',
    'log_files': 'low',
    'installer_cache': 'low',
    'pip_cache': 'low',
    'npm_cache': 'low',
    'yarn_cache': 'low',
    'maven_repo': 'medium',
    'gradle_cache': 'medium',
    'conda_pkgs': 'low',
    'jdk_versions': 'high',
    'thumbnails': 'low',
    'error_reports': 'low',
    'delivery_opt': 'low',
    'recycle_bin': 'low'
}

for idx, p in enumerate(CUSTOM_CACHE_DIRS):
    if p.exists():
        RISK_MAP[f'custom_{idx}'] = 'low'

_last_freed_gb = 0.0

def _parse_version(dirname: str) -> tuple:
    nums = re.findall(r'\d+', dirname)
    if not nums:
        return (0,)
    return tuple(int(n) for n in nums)

def _get_backup_zip_path() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return BACKUP_DIR / f"CleanSlate_Backup_{timestamp}.zip"

def _get_folder_total_size(path: Path) -> int:
    total = 0
    for f in path.rglob('*'):
        if f.is_file():
            try:
                total += f.stat().st_size
            except (OSError, PermissionError):
                pass
    return total

def _backup_to_zip(file_paths, zip_path) -> bool:
    total_size = 0
    for p in file_paths:
        if p.exists():
            total_size += _get_folder_total_size(p)
    if total_size > 8 * 1024 ** 3:
        _log_clean("BACKUP_SKIP", str(zip_path), f"跳过备份 (大小 {_get_size_gb(total_size):.2f} GB 超过8GB)")
        print(f"警告: 备份大小 {_get_size_gb(total_size):.2f} GB 超过8GB，跳过备份")
        return False
    try:
        import zipfile
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for p in file_paths:
                if not p.exists():
                    continue
                if p.is_file():
                    zf.write(p, p.name)
                elif p.is_dir():
                    for root, dirs, files in os.walk(p):
                        for f in files:
                            full_path = Path(root) / f
                            arc_name = full_path.relative_to(p.parent)
                            zf.write(full_path, arc_name)
        return True
    except Exception:
        return False

def _log_clean(action: str, path: str, result: str, backup_path: str = ""):
    log_file = BACKUP_DIR / 'clean.log'
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {action} | {path} | {result}")
            if backup_path:
                f.write(f" | 备份: {backup_path}")
            f.write("\n")
    except Exception:
        pass

def _get_size_gb(size_bytes: int) -> float:
    return round(size_bytes / (1024 ** 3), 2)

def _send_to_recycle_bin(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        path_str = str(path.resolve()) + '\0\0'
        SHFileOperationW = ctypes.windll.shell32.SHFileOperationW
        SHFileOperationW.argtypes = [ctypes.POINTER(wintypes.SHFILEOPSTRUCTW)]
        file_op = wintypes.SHFILEOPSTRUCTW()
        file_op.wFunc = 2
        file_op.pFrom = ctypes.create_unicode_buffer(path_str)
        file_op.fFlags = 0x0001 | 0x0004 | 0x0008
        file_op.hwnd = None
        result = SHFileOperationW(ctypes.byref(file_op))
        return result == 0
    except Exception:
        try:
            shutil.rmtree(path, ignore_errors=True)
            return True
        except Exception:
            return False

def _delete_folder(path: Path, item_id: str = None) -> bool:
    global _last_freed_gb
    if not path.exists():
        return True
    risk = RISK_MAP.get(item_id, 'low')
    force_backup = risk in ('medium', 'high')
    backup_path = ""
    if not EMERGENCY_MODE and (force_backup or (BACKUP_ENABLED and risk == 'low')):
        file_paths = [path]
        zip_path = _get_backup_zip_path()
        if _backup_to_zip(file_paths, zip_path):
            backup_path = str(zip_path)
    try:
        if RECYCLE_BIN_ENABLED:
            print(f"  正在移至回收站，请耐心等待...")
            all_files = list(path.rglob('*'))
            file_list = [f for f in all_files if f.is_file()]
            total = len(file_list)
            success_count = 0
            freed_size = 0
            for f in file_list:
                try:
                    size = f.stat().st_size
                    if _send_to_recycle_bin(f):
                        success_count += 1
                        freed_size += size
                except Exception:
                    pass
            print()
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
                path.mkdir(parents=True, exist_ok=True)
            _log_clean("DELETE_FOLDER", str(path), f"成功（回收站）{success_count}/{total}", backup_path)
            freed_gb = _get_size_gb(freed_size)
            _last_freed_gb = freed_gb
            print(f"  回收站操作完成：成功移动 {success_count} 个文件，释放 {freed_gb} GB")
            return True
        else:
            print(f"  正在删除文件，请耐心等待（不要退出窗口）...")
            all_files = list(path.rglob('*'))
            file_list = [f for f in all_files if f.is_file()]
            total = len(file_list)
            if total == 0:
                shutil.rmtree(path, ignore_errors=True)
                path.mkdir(parents=True, exist_ok=True)
                _log_clean("DELETE_FOLDER", str(path), "成功 (无文件)", backup_path)
                _last_freed_gb = 0.0
                print("  清理完成：无文件可删除")
                return True
            deleted = 0
            freed_size = 0
            for f in file_list:
                try:
                    size = f.stat().st_size
                    f.unlink()
                    deleted += 1
                    freed_size += size
                except Exception:
                    pass
            print()
            try:
                shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            _log_clean("DELETE_FOLDER", str(path), f"成功 (删除了 {deleted} 个文件)", backup_path)
            freed_gb = _get_size_gb(freed_size)
            _last_freed_gb = freed_gb
            print(f"  清理完成：删除了 {deleted} 个文件，释放了 {freed_gb} GB")
            return True
    except Exception as e:
        _log_clean("DELETE_FOLDER", str(path), f"失败: {str(e)}", backup_path)
        return False

def _delete_files(path: Path, item_id: str = None) -> bool:
    global _last_freed_gb
    if not path.exists():
        return True
    risk = RISK_MAP.get(item_id, 'low')
    force_backup = risk in ('medium', 'high')
    backup_path = ""
    if not EMERGENCY_MODE and (force_backup or (BACKUP_ENABLED and risk == 'low')):
        file_paths = list(path.glob('*'))
        if file_paths:
            zip_path = _get_backup_zip_path()
            if _backup_to_zip(file_paths, zip_path):
                backup_path = str(zip_path)
    try:
        file_list = [f for f in path.glob('*') if f.is_file()]
        total = len(file_list)
        if RECYCLE_BIN_ENABLED:
            print(f"  正在移至回收站，请耐心等待...")
            success_count = 0
            freed_size = 0
            for f in file_list:
                try:
                    size = f.stat().st_size
                    if _send_to_recycle_bin(f):
                        success_count += 1
                        freed_size += size
                except Exception:
                    pass
            print()
            _log_clean("DELETE_FILES", str(path), f"成功（回收站）{success_count}/{total}", backup_path)
            freed_gb = _get_size_gb(freed_size)
            _last_freed_gb = freed_gb
            print(f"  回收站操作完成：成功移动 {success_count} 个文件，释放 {freed_gb} GB")
            return True
        else:
            if total == 0:
                _log_clean("DELETE_FILES", str(path), "成功 (无文件)", backup_path)
                _last_freed_gb = 0.0
                print("  清理完成：无文件可删除")
                return True
            print(f"  正在删除文件，请耐心等待...")
            deleted = 0
            freed_size = 0
            for f in file_list:
                try:
                    size = f.stat().st_size
                    f.unlink()
                    deleted += 1
                    freed_size += size
                except Exception:
                    pass
            print()
            _log_clean("DELETE_FILES", str(path), f"成功 (删除了 {deleted} 个文件)", backup_path)
            freed_gb = _get_size_gb(freed_size)
            _last_freed_gb = freed_gb
            print(f"  清理完成：删除了 {deleted} 个文件，释放了 {freed_gb} GB")
            return True
    except Exception as e:
        _log_clean("DELETE_FILES", str(path), f"失败: {str(e)}", backup_path)
        return False

def _run_cmd(cmd: str) -> bool:
    try:
        return subprocess.run(cmd, shell=True, capture_output=True).returncode == 0
    except Exception:
        return False

def clean_shadow_storage(item_id: str = None) -> bool:
    global _last_freed_gb
    result = _run_cmd("vssadmin delete shadows /all /quiet")
    _log_clean("SHADOW", "系统还原点", "成功" if result else "失败")
    _last_freed_gb = 0.0
    return result

def clean_winsxs(item_id: str = None) -> bool:
    global _last_freed_gb
    print("\n" + "=" * 70)
    print("警告：此操作将永久删除系统更新备份")
    print("执行后，已安装的 Windows 更新将无法卸载回滚")
    print("如果系统出现兼容性问题，无法通过卸载更新修复")
    print("请确认系统已稳定运行超过一个月，所有驱动和软件都正常")
    print("=" * 70)
    confirm = input("输入 'yes' 确认执行，否则取消: ").strip().lower()
    if confirm != 'yes':
        print("已取消 WinSxS 清理")
        _log_clean("WINSXS", "WinSxS 组件存储", "已取消")
        _last_freed_gb = 0.0
        return False
    result = _run_cmd("Dism /Online /Cleanup-Image /StartComponentCleanup /ResetBase")
    _log_clean("WINSXS", "WinSxS 组件存储", "成功" if result else "失败")
    if result:
        try:
            out = subprocess.run("Dism /Online /Cleanup-Image /AnalyzeComponentStore", shell=True, capture_output=True, text=True).stdout
        except Exception:
            out = ""
        m = re.search(r"组件存储的实际大小\s*:\s*([\d.]+)\s*MB", out)
        if m:
            freed_mb = float(m.group(1))
            _last_freed_gb = round(freed_mb / 1024, 2)
        else:
            _last_freed_gb = 0.0
    else:
        _last_freed_gb = 0.0
    return result

def clean_temp_system(item_id: str = None) -> bool:
    return _delete_folder(PATH_TEMP_SYSTEM, item_id)

def clean_temp_user(item_id: str = None) -> bool:
    return _delete_folder(PATH_TEMP_USER, item_id)

def clean_prefetch(item_id: str = None) -> bool:
    return _delete_files(PATH_PREFETCH, item_id)

def clean_update_cache(item_id: str = None) -> bool:
    return _delete_folder(PATH_UPDATE_CACHE, item_id)

def clean_qq_residue(item_id: str = None) -> bool:
    return _delete_folder(PATH_QQ, item_id)

def clean_wechat_cache(item_id: str = None) -> bool:
    global _last_freed_gb
    print("微信缓存建议在微信客户端中手动清理 (设置 -> 文件管理 -> 清理缓存)")
    _log_clean("WECHAT", "微信缓存", "跳过，建议手动清理")
    _last_freed_gb = 0.0
    return False

def clean_hibernation(item_id: str = None) -> bool:
    global _last_freed_gb
    print("\n关闭休眠将释放磁盘空间，但系统将无法使用休眠功能")
    confirm = input("确认关闭休眠？(y/N): ").strip().lower()
    if confirm != 'y':
        print("已取消关闭休眠")
        _log_clean("HIBERNATION", "休眠文件", "已取消")
        _last_freed_gb = 0.0
        return False
    result = _run_cmd("powercfg -h off")
    _log_clean("HIBERNATION", "休眠文件", "成功" if result else "失败")
    _last_freed_gb = 0.0
    return result

def clean_duplicate_files(item_id: str = None) -> bool:
    global _last_freed_gb
    print("重复文件清理：将删除重复文件，保留第一个")
    target_dirs = [
        USER_HOME / 'Documents',
        USER_HOME / 'Downloads',
        USER_HOME / 'Desktop',
        USER_HOME / 'Pictures',
        USER_HOME / 'Music',
        USER_HOME / 'Videos',
    ]
    size_map = {}
    for base in target_dirs:
        if not base.exists():
            continue
        for f in base.rglob('*'):
            if f.is_file() and f.stat().st_size > 1024:
                size = f.stat().st_size
                if size not in size_map:
                    size_map[size] = []
                size_map[size].append(f)
    hashes = {}
    deleted_count = 0
    freed_size = 0
    for size, files in size_map.items():
        if len(files) < 2:
            continue
        for f in files:
            file_hash = _get_file_hash_sample(f)
            if not file_hash:
                continue
            if file_hash in hashes:
                try:
                    sz = f.stat().st_size
                    f.unlink()
                    deleted_count += 1
                    freed_size += sz
                    _log_clean("DUPLICATE_DELETE", str(f), "成功")
                except Exception:
                    pass
            else:
                hashes[file_hash] = f
    _log_clean("DUPLICATE_FILES", f"重复文件", f"删除 {deleted_count} 个")
    freed_gb = _get_size_gb(freed_size)
    _last_freed_gb = freed_gb
    print(f"删除重复文件 {deleted_count} 个，释放 {freed_gb} GB")
    return True

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
"""
def clean_large_files(item_id: str = None) -> bool:
    global _last_freed_gb
    target_dirs = [
        USER_HOME,
        Path(f'{SYSTEM_DRIVE}/Program Files'),
        Path(f'{SYSTEM_DRIVE}/Program Files (x86)'),
    ]
    large_files = []
    for base in target_dirs:
        if not base.exists():
            continue
        for f in base.rglob('*'):
            if f.is_file():
                try:
                    if f.stat().st_size > 1024 ** 3:
                        large_files.append(f)
                except (OSError, PermissionError):
                    pass
    if not large_files:
        print("没有大文件可清理")
        _last_freed_gb = 0.0
        return True
    deleted_count = 0
    freed_size = 0
    for f in large_files:
        sz_gb = _get_size_gb(f.stat().st_size)
        print(f"  {f} ({sz_gb:.2f} GB)")
        confirm = input("删除此文件？(y/N): ").strip().lower()
        if confirm == 'y':
            try:
                sz = f.stat().st_size
                f.unlink()
                deleted_count += 1
                freed_size += sz
                _log_clean("LARGE_FILE_DELETE", str(f), "成功")
            except Exception as e:
                _log_clean("LARGE_FILE_DELETE", str(f), f"失败: {str(e)}")
    _log_clean("LARGE_FILES", f"大文件", f"删除 {deleted_count} 个")
    freed_gb = _get_size_gb(freed_size)
    _last_freed_gb = freed_gb
    print(f"删除大文件 {deleted_count} 个，释放 {freed_gb} GB")
    return True
"""
def clean_empty_folders(item_id: str = None) -> bool:
    global _last_freed_gb
    target_dirs = [
        USER_HOME / 'Documents',
        USER_HOME / 'Downloads',
        USER_HOME / 'Desktop',
        USER_HOME / 'Pictures',
        USER_HOME / 'Music',
        USER_HOME / 'Videos',
        Path(f'{SYSTEM_DRIVE}/Users/Public'),
    ]
    total_deleted = 0
    while True:
        deleted_this_round = 0
        for base in target_dirs:
            if not base.exists():
                continue
            for dirpath, dirnames, filenames in os.walk(base, topdown=False):
                if not filenames and not dirnames:
                    try:
                        os.rmdir(dirpath)
                        deleted_this_round += 1
                    except OSError:
                        pass
        if deleted_this_round == 0:
            break
        total_deleted += deleted_this_round
    _log_clean("EMPTY_FOLDERS", f"空文件夹", f"删除 {total_deleted} 个")
    _last_freed_gb = 0.0
    print(f"删除空文件夹 {total_deleted} 个")
    return True

def clean_browser_cache(item_id: str = None) -> bool:
    dirs = [PATH_CHROME_CACHE, PATH_EDGE_CACHE]
    if PATH_FIREFOX_CACHE.exists():
        for profile in PATH_FIREFOX_CACHE.glob('*.default*'):
            cache_dir = profile / 'cache2'
            if cache_dir.exists():
                dirs.append(cache_dir)
    ok = True
    for p in dirs:
        if p.exists():
            ok &= _delete_folder(p, item_id)
    return ok

def clean_ide_cache(item_id: str = None) -> bool:
    dirs = []
    if PATH_VSCODE_CACHE.exists():
        dirs.append(PATH_VSCODE_CACHE)
    for p in PATH_PYCHARM_CACHE.parent.glob('PyCharm*'):
        cache_dir = p / 'cache'
        if cache_dir.exists():
            dirs.append(cache_dir)
    for p in PATH_INTELLIJ_CACHE.parent.glob('IntelliJIdea*'):
        cache_dir = p / 'cache'
        if cache_dir.exists():
            dirs.append(cache_dir)
    ok = True
    for p in dirs:
        ok &= _delete_folder(p, item_id)
    return ok

def clean_log_files(item_id: str = None) -> bool:
    global _last_freed_gb
    p = PATH_SYSTEM_LOGS
    if not p.exists():
        _last_freed_gb = 0.0
        return True
    now = time.time()
    cutoff = now - 30 * 24 * 3600
    deleted = 0
    freed_size = 0
    extensions = ('.log', '.etl', '.evtx')
    for ext in extensions:
        for f in p.rglob(f'*{ext}'):
            if f.is_file():
                try:
                    if f.stat().st_mtime < cutoff:
                        sz = f.stat().st_size
                        f.unlink()
                        deleted += 1
                        freed_size += sz
                except OSError:
                    pass
    _log_clean("LOG_FILES", f"日志文件", f"删除 {deleted} 个")
    freed_gb = _get_size_gb(freed_size)
    _last_freed_gb = freed_gb
    print(f"删除日志文件 {deleted} 个，释放 {freed_gb} GB")
    return True

def clean_installer_cache(item_id: str = None) -> bool:
    p = PATH_INSTALLER_CACHE
    if p.exists():
        return _delete_folder(p, item_id)
    return True

def clean_pip_cache(item_id: str = None) -> bool:
    p = PATH_PIP_CACHE
    if p.exists():
        return _delete_folder(p, item_id)
    return True

def clean_npm_cache(item_id: str = None) -> bool:
    p = PATH_NPM_CACHE
    if p.exists():
        return _delete_folder(p, item_id)
    return True

def clean_yarn_cache(item_id: str = None) -> bool:
    p = PATH_YARN_CACHE
    if p.exists():
        return _delete_folder(p, item_id)
    return True

def clean_maven_repo(item_id: str = None) -> bool:
    p = PATH_MAVEN_REPO
    if p.exists():
        return _delete_folder(p, item_id)
    return True

def clean_gradle_cache(item_id: str = None) -> bool:
    p = PATH_GRADLE_CACHE
    if p.exists():
        return _delete_folder(p, item_id)
    return True

def clean_conda_pkgs(item_id: str = None) -> bool:
    p = PATH_CONDA_PKGS
    if p.exists():
        return _delete_folder(p, item_id)
    return True

def clean_jdk_versions(item_id: str = None) -> bool:
    all_jdks = []
    for base in PATH_JDK_INSTALLS:
        if not base.exists():
            continue
        for item in base.glob('jdk*'):
            if item.is_dir():
                all_jdks.append(item)
    if len(all_jdks) <= 1:
        return True
    all_jdks.sort(key=lambda x: _parse_version(x.name))
    latest = all_jdks[-1]
    deleted = 0
    for p in all_jdks[:-1]:
        try:
            if _delete_folder(p, item_id):
                deleted += 1
        except Exception:
            pass
    _log_clean("JDK", f"删除 {deleted} 个旧版本，保留 {latest.name}", "完成")
    print(f"删除 {deleted} 个旧版本 JDK，保留 {latest.name}")
    return True

def clean_thumbnails(item_id: str = None) -> bool:
    global _last_freed_gb
    p = USER_HOME / 'AppData/Local/Microsoft/Windows/Explorer'
    deleted = 0
    freed_size = 0
    if p.exists():
        for f in p.glob('thumbcache_*.db'):
            try:
                sz = f.stat().st_size
                f.unlink()
                deleted += 1
                freed_size += sz
            except Exception:
                pass
    _log_clean("THUMBNAILS", str(p), f"删除 {deleted} 个缩略图缓存文件")
    freed_gb = _get_size_gb(freed_size)
    _last_freed_gb = freed_gb
    print(f"删除缩略图缓存 {deleted} 个，释放 {freed_gb} GB")
    return True

def clean_error_reports(item_id: str = None) -> bool:
    global _last_freed_gb
    paths = [
        USER_HOME / 'AppData/Local/Microsoft/Windows/WER',
        Path(f'{SYSTEM_DRIVE}/ProgramData/Microsoft/Windows/WER'),
    ]
    ok = True
    for p in paths:
        if p.exists():
            try:
                shutil.rmtree(p, ignore_errors=True)
                p.mkdir(parents=True, exist_ok=True)
                _log_clean("ERROR_REPORTS", str(p), "成功")
            except Exception as e:
                _log_clean("ERROR_REPORTS", str(p), f"失败: {e}")
                ok = False
    _last_freed_gb = 0.0
    print("清理 Windows 错误报告完成")
    return ok

def clean_delivery_opt(item_id: str = None) -> bool:
    global _last_freed_gb
    p = Path(f'{SYSTEM_DRIVE}/Windows/SoftwareDistribution/DeliveryOptimization')
    if not p.exists():
        _last_freed_gb = 0.0
        return True
    try:
        shutil.rmtree(p, ignore_errors=True)
        p.mkdir(parents=True, exist_ok=True)
        _log_clean("DELIVERY_OPT", str(p), "成功")
        _last_freed_gb = 0.0
        print("清理传递优化文件完成")
        return True
    except Exception as e:
        _log_clean("DELIVERY_OPT", str(p), f"失败: {e}")
        _last_freed_gb = 0.0
        return False

def clean_recycle_bin(item_id: str = None) -> bool:
    global _last_freed_gb
    result = _run_cmd("powershell -Command \"Clear-RecycleBin -Force\"")
    _log_clean("RECYCLE_BIN", "回收站", "成功" if result else "失败")
    if result:
        print("回收站已清空")
    else:
        print("回收站清空失败，但可能已部分清理")
    _last_freed_gb = 0.0
    return True

CLEAN_MAP = {
    'shadow': clean_shadow_storage,
    'winsxs': clean_winsxs,
    'temp_sys': clean_temp_system,
    'temp_user': clean_temp_user,
    'prefetch': clean_prefetch,
    'update_cache': clean_update_cache,
    'qq_residue': clean_qq_residue,
    'wechat_cache': clean_wechat_cache,
    'hibernation': clean_hibernation,
    'duplicate_files': clean_duplicate_files,
    #'large_files': clean_large_files,
    'empty_folders': clean_empty_folders,
    'browser_cache': clean_browser_cache,
    'ide_cache': clean_ide_cache,
    'log_files': clean_log_files,
    'installer_cache': clean_installer_cache,
    'pip_cache': clean_pip_cache,
    'npm_cache': clean_npm_cache,
    'yarn_cache': clean_yarn_cache,
    'maven_repo': clean_maven_repo,
    'gradle_cache': clean_gradle_cache,
    'conda_pkgs': clean_conda_pkgs,
    'jdk_versions': clean_jdk_versions,
    'thumbnails': clean_thumbnails,
    'error_reports': clean_error_reports,
    'delivery_opt': clean_delivery_opt,
    'recycle_bin': clean_recycle_bin
}

for idx, p in enumerate(CUSTOM_CACHE_DIRS):
    if p.exists():
        def make_custom_cleaner(dir_path):
            return lambda item_id=None: _delete_folder(dir_path, item_id)
        CLEAN_MAP[f'custom_{idx}'] = make_custom_cleaner(p)

def run_cleaner(item_id: str) -> Dict[str, bool]:
    global _last_freed_gb
    func = CLEAN_MAP.get(item_id)
    if not func:
        return {"success": False, "message": f"未知任务 {item_id}", "freed_gb": 0.0}

    risk = RISK_MAP.get(item_id, 'low')
    if EMERGENCY_MODE and risk == 'high':
        return {"success": True, "message": "降级模式跳过（高风险）", "freed_gb": 0.0}

    _last_freed_gb = 0.0
    try:
        ok = func(item_id)
        freed_gb = _last_freed_gb
        return {"success": ok, "message": "完成" if ok else "失败", "freed_gb": freed_gb}
    except Exception as e:
        return {"success": False, "message": f"异常: {str(e)}", "freed_gb": 0.0}