# Edge 缓存专清补丁 - edge缓存默认目录专清，你要是把edge装到别的地方我也没辙喽~
# 加载后获得永久vip——开玩笑本软件木有会员系统（其实是作者不会写◐⩊◑  ྀི），自动存在补丁目录

import os
from pathlib import Path

def _get_size_gb(size_bytes):
    return round(size_bytes / (1024 ** 3), 2)

def _get_folder_size(path):
    total = 0
    if not path.exists():
        return total
    for f in path.rglob('*'):
        if f.is_file():
            try:
                total += f.stat().st_size
            except (OSError, PermissionError):
                pass
    return total

def scan(patch_id='edge_cache_patch', patch_name='Edge 缓存专清', patch_risk='low'):
    user_home = Path(os.environ.get('USERPROFILE', 'C:\\Users\\Administrator'))
    target_dirs = [
        user_home / 'AppData/Local/Microsoft/Edge/User Data/Default/Cache',
        user_home / 'AppData/Local/Microsoft/Edge/User Data/Default/Code Cache',
    ]
    total_size = 0
    all_files = []
    for d in target_dirs:
        if d.exists():
            size = _get_folder_size(d)
            if size > 0:
                total_size += size
                for f in d.rglob('*'):
                    if f.is_file():
                        all_files.append(f)
    size_gb = _get_size_gb(total_size)
    return {
        'id': patch_id,
        'name': patch_name,
        'risk': patch_risk,
        'size_gb': size_gb,
        'can_clean': size_gb > 0.01,
        'detail': f'Edge 浏览器缓存，占用 {size_gb:.2f} GB',
        '_files': all_files
    }

_last_result = {}

def clean(item_id):
    global _last_result
    files = _last_result.get('_files', [])
    if not files:
        print('没有 Edge 缓存文件可清理（请先执行扫描）')
        return False
    deleted = 0
    for f in files:
        try:
            f.unlink()
            deleted += 1
        except Exception:
            pass
    _last_result['_files'] = []
    print(f'清理 Edge 缓存文件 {deleted} 个')
    return deleted > 0

def register_patch():
    global _last_result
    _last_result = scan()
    return {
        'id': 'edge_cache_patch',
        'name': 'Edge 缓存专清',
        'risk': 'low',
        'scan': lambda: _last_result,
        'clean': clean
    }