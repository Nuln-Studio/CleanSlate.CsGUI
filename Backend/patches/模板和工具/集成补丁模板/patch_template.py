# 永久加载的集成补丁，只跑一次，集成进程序注册表，一次跑完高枕无忧，多次清理轻松无压(◦˙▽˙◦)

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

def scan(patch_id='patch_template', patch_name='自定义集成补丁', patch_risk='low'):
    user_home = Path(os.environ.get('USERPROFILE', 'C:\\Users\\Administrator'))
    target_dirs = [
        #填入要扫描清理的目录
        #如果你想清缓存,建议这个格式（相对路径模式）
            #user_home / '填文件夹相对路径',
        #如果你想一劳永逸,建议用这个通用写法，它只看绝对路径
            #Path('填绝对路径'),
        #当然，支持多写法多目录混用
        #比如这样：
            #user_home / 'Downloads',
            #user_home / 'Desktop',
            #Path('D:/MyCache'),
            #Path('C:/Windows/Temp'),
        #注意缩进，与本注释同列即可（示例为查看方便）
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
        'detail': f'占用 {size_gb:.2f} GB',
        '_files': all_files
    }

_last_result = {}

def clean(item_id):
    global _last_result
    files = _last_result.get('_files', [])
    if not files:
        print('没有文件可清理')
        return False
    deleted = 0
    for f in files:
        try:
            f.unlink()
            deleted += 1
        except Exception:
            pass
    print(f'删了 {deleted} 个文件')
    return deleted > 0

def register_patch():
    return {
        'id': 'patch_template',
        'name': '自定义集成补丁',
        'risk': 'low',
        'scan': scan,
        'clean': clean
    }