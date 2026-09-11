# 临时补丁，只干一次，不能高振无忧¯꒳¯

import os
from pathlib import Path

def _get_size_gb(size_bytes):
    return round(size_bytes / (1024 ** 3), 2)

def execute_once():
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
    file_count = 0
    for d in target_dirs:
        if d.exists():
            for f in d.rglob('*'):
                if f.is_file():
                    try:
                        sz = f.stat().st_size
                        total_size += sz
                        f.unlink()
                        file_count += 1
                    except Exception:
                        pass
    return {
        'cleaned_size': f'{_get_size_gb(total_size)} GB',
        'file_count': file_count
    }