#配置文件内容改之前先群里@一下我，改之前先备份
import os
import yaml
from pathlib import Path
import sys
import shutil
SYSTEM_DRIVE = os.environ.get('SystemDrive', 'C:')
CURRENT_USER = os.environ.get('USERNAME', 'Administrator')
USER_HOME = Path(os.environ.get('USERPROFILE', f'{SYSTEM_DRIVE}\\Users\\{CURRENT_USER}'))
def _find_best_base_dir():
    d_path = Path('D:/ClSl')
    if d_path.parent.exists():
        try:
            usage = shutil.disk_usage(d_path.parent)
            if usage.free > 1 * 1024 ** 3:
                return d_path
        except:
            pass
    best_drive = None
    best_free = -1
    for letter in 'DEFGHIJKLMNOPQRSTUVWXYZ':
        drive_path = Path(f'{letter}:/')
        if not drive_path.exists():
            continue
        try:
            usage = shutil.disk_usage(drive_path)
            if usage.free > best_free and usage.free >= 500 * 1024 ** 2:
                best_free = usage.free
                best_drive = drive_path
        except:
            continue
    if best_drive:
        return best_drive / 'ClSl'
    c_path = Path('C:/ClSl')
    try:
        c_path.mkdir(parents=True, exist_ok=True)
        c_path.rmdir()
        return c_path
    except:
        if getattr(sys, 'frozen', False):
            return Path(sys.executable).parent / 'ClSl'
        else:
            return Path(__file__).parent / 'ClSl'
BASE_DIR = _find_best_base_dir()
CONFIG_FILE = BASE_DIR / 'config.yaml'
EMERGENCY_MODE = False
if BASE_DIR.drive == 'C:':
    try:
        usage = shutil.disk_usage('C:')
        if usage.free < 2 * 1024 ** 3:
            EMERGENCY_MODE = True
    except Exception:
        pass
def load_config():
    default = {
        "check_update": False,
        "custom_cache_dirs": [],
        "recycle_bin": {
            "enabled": False
        },
        "backup": {
            "enabled": True,
            "dir": str(BASE_DIR / 'backup')
        },
        "aggressive_mode_enabled": False,
        "enable_patch": False,
        "patch_dir": str(BASE_DIR / 'patches'),
        "scanner": {
            "shadow": False,
            "winsxs": False,
            "temp_sys": True,
            "temp_user": True,
            "prefetch": True,
            "update_cache": True,
            "qq_residue": True,
            "wechat_cache": True,
            "hibernation": True,
            "duplicate_files": True,
            #"large_files": True,
            "empty_folders": True,
            "browser_cache": True,
            "ide_cache": True,
            "log_files": True,
            "installer_cache": True,
            "pip_cache": True,
            "npm_cache": True,
            "yarn_cache": True,
            "maven_repo": True,
            "gradle_cache": True,
            "conda_pkgs": True,
            "jdk_versions": True,
            "thumbnails": True,
            "error_reports": True,
            "delivery_opt": True,
            "recycle_bin": True
        }
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)
            if cfg is None:
                cfg = {}
            for key in default:
                if key not in cfg:
                    cfg[key] = default[key]
            if "scanner" not in cfg:
                cfg["scanner"] = default["scanner"]
            else:
                for key in default["scanner"]:
                    if key not in cfg["scanner"]:
                        cfg["scanner"][key] = default["scanner"][key]
            return cfg
        except Exception as e:
            print(f"[Config] 配置文件解析失败，使用默认配置: {e}")
            return default
    else:
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                f.write(f"""check_update: false  # true启动检查更新，false跳过程序启动时的联网版本检查
custom_cache_dirs: []  # 自定义缓存目录列表
recycle_bin:
  enabled: false  # false 不走回收站，直接删除（释放空间）
scanner:  #扫描时是否启用这些选项（大文件不可用）
  shadow: false          # 系统还原点
  winsxs: false          # WinSxS 组件存储
  temp_sys: true        # 系统临时文件
  temp_user: true       # 用户临时文件
  prefetch: true        # 预读缓存
  update_cache: true    # Windows 更新缓存
  qq_residue: true      # QQ 残留
  wechat_cache: true    # 微信缓存
  hibernation: true     # 休眠文件
  duplicate_files: true # 重复文件
  large_files: false    # 大文件 (不可用，改成true也没用)
  empty_folders: true   # 空文件夹
  browser_cache: true   # 浏览器缓存
  ide_cache: true       # IDE 缓存
  log_files: true       # 日志文件
  installer_cache: true # 安装包缓存
  pip_cache: true       # pip 缓存
  npm_cache: true      # npm 缓存
  yarn_cache: true      # yarn 缓存
  maven_repo: true      # Maven 本地仓库
  gradle_cache: true    # Gradle 缓存
  conda_pkgs: true      # Conda 包缓存
  jdk_versions: true    # JDK 多版本残留
  thumbnails: true      # 缩略图缓存
  error_reports: true   # Windows错误报告
  delivery_opt: true    # 传递优化文件
  recycle_bin: true     # 回收站
backup:
  enabled: true  # true 删除前自动备份，false 不备份（中高风险项强制备份）
  dir: "{(BASE_DIR / 'backup').as_posix()}"  # 备份根目录，不存在会自动创建（优先D盘，没有会尝试找其他盘符，其他盘符也没有就存C盘了）
aggressive_mode_enabled: false  # true 显示激进模式选项，false 只显示安全模式
enable_patch: false  # true 显示补丁加载选项，false 隐藏
""")
            print(f"[Config] 已生成配置文件: {CONFIG_FILE}")
            print("[Config] 如需自定义清理行为，请修改 config.yaml")
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                new_cfg = yaml.safe_load(f)
            return new_cfg
        except Exception:
            pass
        return default
CONFIG = load_config()
CHECK_UPDATE = CONFIG.get("check_update", False)
CUSTOM_CACHE_DIRS = [Path(p) for p in CONFIG.get("custom_cache_dirs", []) if p]
RECYCLE_BIN_ENABLED = CONFIG.get("recycle_bin", {}).get("enabled", False)
BACKUP_ENABLED = CONFIG.get("backup", {}).get("enabled", True)
BACKUP_DIR = Path(CONFIG.get("backup", {}).get("dir", str(BASE_DIR / 'backup')))
AGGRESSIVE_MODE_ENABLED = CONFIG.get("aggressive_mode_enabled", False)
ENABLE_PATCH = CONFIG.get("enable_patch", False)
BACKUP_RETENTION_DAYS = CONFIG.get("backup", {}).get("retention_days", 30)
PATCH_DIR = Path(CONFIG.get("patch_dir", str(BASE_DIR / 'patches')))
_SCANNER = CONFIG.get("scanner", {})
ENABLE_SHADOW = _SCANNER.get("shadow", False)
ENABLE_WINSXS = _SCANNER.get("winsxs", False)
ENABLE_TEMP_SYS = _SCANNER.get("temp_sys", True)
ENABLE_TEMP_USER = _SCANNER.get("temp_user", True)
ENABLE_PREFETCH = _SCANNER.get("prefetch", True)
ENABLE_UPDATE_CACHE = _SCANNER.get("update_cache", True)
ENABLE_QQ_RESIDUE = _SCANNER.get("qq_residue", True)
ENABLE_WECHAT_CACHE = _SCANNER.get("wechat_cache", True)
ENABLE_HIBERNATION = _SCANNER.get("hibernation", True)
ENABLE_DUPLICATE_FILES = _SCANNER.get("duplicate_files", True)
#ENABLE_LARGE_FILES = _SCANNER.get("large_files", True)
ENABLE_EMPTY_FOLDERS = _SCANNER.get("empty_folders", True)
ENABLE_BROWSER_CACHE = _SCANNER.get("browser_cache", True)
ENABLE_IDE_CACHE = _SCANNER.get("ide_cache", True)
ENABLE_LOG_FILES = _SCANNER.get("log_files", True)
ENABLE_INSTALLER_CACHE = _SCANNER.get("installer_cache", True)
ENABLE_PIP_CACHE = _SCANNER.get("pip_cache", True)
ENABLE_NPM_CACHE = _SCANNER.get("npm_cache", True)
ENABLE_YARN_CACHE = _SCANNER.get("yarn_cache", True)
ENABLE_MAVEN_REPO = _SCANNER.get("maven_repo", True)
ENABLE_GRADLE_CACHE = _SCANNER.get("gradle_cache", True)
ENABLE_CONDA_PKGS = _SCANNER.get("conda_pkgs", True)
ENABLE_JDK_VERSIONS = _SCANNER.get("jdk_versions", True)
ENABLE_THUMBNAILS = _SCANNER.get("thumbnails", True)
ENABLE_ERROR_REPORTS = _SCANNER.get("error_reports", True)
ENABLE_DELIVERY_OPT = _SCANNER.get("delivery_opt", True)
ENABLE_RECYCLE_BIN = _SCANNER.get("recycle_bin", True)
PATH_TEMP_SYSTEM = Path(f'{SYSTEM_DRIVE}/Windows/Temp')
PATH_TEMP_USER = Path(os.environ.get('TEMP', f'{SYSTEM_DRIVE}\\Users\\{CURRENT_USER}\\AppData\\Local\\Temp'))
PATH_PREFETCH = Path(f'{SYSTEM_DRIVE}/Windows/Prefetch')
PATH_UPDATE_CACHE = Path(f'{SYSTEM_DRIVE}/Windows/SoftwareDistribution/Download')
PATH_DOCUMENTS = USER_HOME / 'Documents'
PATH_QQ = PATH_DOCUMENTS / 'Tencent Files'
PATH_WECHAT_CANDIDATES = [
    PATH_DOCUMENTS / 'WeChat Files',
    Path(f'{SYSTEM_DRIVE}/wx'),
    Path(f'{SYSTEM_DRIVE}/WeChat'),
]
PATH_HIBERNATION = Path(f'{SYSTEM_DRIVE}/hiberfil.sys')
PATH_CHROME_CACHE = USER_HOME / 'AppData/Local/Google/Chrome/User Data/Default/Cache'
PATH_EDGE_CACHE = USER_HOME / 'AppData/Local/Microsoft/Edge/User Data/Default/Cache'
PATH_FIREFOX_CACHE = USER_HOME / 'AppData/Local/Mozilla/Firefox/Profiles'
PATH_VSCODE_CACHE = USER_HOME / 'AppData/Roaming/Code/Cache'
PATH_PYCHARM_CACHE = USER_HOME / 'AppData/Local/JetBrains/PyCharm*/cache'
PATH_INTELLIJ_CACHE = USER_HOME / 'AppData/Local/JetBrains/IntelliJIdea*/cache'
PATH_SYSTEM_LOGS = Path(f'{SYSTEM_DRIVE}/Windows/Logs')
PATH_INSTALLER_CACHE = Path(f'{SYSTEM_DRIVE}/Windows/Installer')
PATH_PIP_CACHE = USER_HOME / 'AppData/Local/pip/cache'
PATH_NPM_CACHE = USER_HOME / 'AppData/Local/npm-cache'
PATH_YARN_CACHE = USER_HOME / 'AppData/Local/Yarn/Cache'
PATH_MAVEN_REPO = USER_HOME / '.m2/repository'
PATH_GRADLE_CACHE = USER_HOME / '.gradle/caches'
PATH_CONDA_PKGS = USER_HOME / '.conda/pkgs'
PATH_JDK_INSTALLS = [
    Path(f'{SYSTEM_DRIVE}/Program Files/Java'),
    Path(f'{SYSTEM_DRIVE}/Program Files (x86)/Java'),
]
_BASE_SCAN_ITEMS = [
    {'id': 'shadow', 'name': '系统还原点', 'risk': 'medium'},
    {'id': 'winsxs', 'name': 'WinSxS 组件存储', 'risk': 'medium'},
    {'id': 'temp_sys', 'name': '系统临时文件', 'risk': 'low'},
    {'id': 'temp_user', 'name': '用户临时文件', 'risk': 'low'},
    {'id': 'prefetch', 'name': '预读缓存', 'risk': 'low'},
    {'id': 'update_cache', 'name': 'Windows 更新缓存', 'risk': 'low'},
    {'id': 'qq_residue', 'name': 'QQ 残留', 'risk': 'low'},
    {'id': 'wechat_cache', 'name': '微信缓存', 'risk': 'low'},
    {'id': 'hibernation', 'name': '休眠文件', 'risk': 'low'},
    {'id': 'duplicate_files', 'name': '重复文件', 'risk': 'medium'},
    #{'id': 'large_files', 'name': '大文件 (>1GB)', 'risk': 'high'},
    {'id': 'empty_folders', 'name': '空文件夹', 'risk': 'low'},
    {'id': 'browser_cache', 'name': '浏览器缓存', 'risk': 'low'},
    {'id': 'ide_cache', 'name': 'IDE 缓存', 'risk': 'low'},
    {'id': 'log_files', 'name': '日志文件 (.log)', 'risk': 'low'},
    {'id': 'installer_cache', 'name': '安装包缓存', 'risk': 'low'},
    {'id': 'pip_cache', 'name': 'pip 缓存', 'risk': 'low'},
    {'id': 'npm_cache', 'name': 'npm 缓存', 'risk': 'low'},
    {'id': 'yarn_cache', 'name': 'yarn 缓存', 'risk': 'low'},
    {'id': 'maven_repo', 'name': 'Maven 本地仓库', 'risk': 'medium'},
    {'id': 'gradle_cache', 'name': 'Gradle 缓存', 'risk': 'medium'},
    {'id': 'conda_pkgs', 'name': 'Conda 包缓存', 'risk': 'low'},
    {'id': 'jdk_versions', 'name': 'JDK 多版本残留', 'risk': 'high'},
    {'id': 'thumbnails', 'name': '缩略图缓存', 'risk': 'low'},
    {'id': 'error_reports', 'name': 'Windows错误报告', 'risk': 'low'},
    {'id': 'delivery_opt', 'name': '传递优化文件', 'risk': 'low'},
    {'id': 'recycle_bin', 'name': '回收站', 'risk': 'low'},
]
ENABLE_MAP = {
    'shadow': ENABLE_SHADOW,
    'winsxs': ENABLE_WINSXS,
    'temp_sys': ENABLE_TEMP_SYS,
    'temp_user': ENABLE_TEMP_USER,
    'prefetch': ENABLE_PREFETCH,
    'update_cache': ENABLE_UPDATE_CACHE,
    'qq_residue': ENABLE_QQ_RESIDUE,
    'wechat_cache': ENABLE_WECHAT_CACHE,
    'hibernation': ENABLE_HIBERNATION,
    'duplicate_files': ENABLE_DUPLICATE_FILES,
    #'large_files': ENABLE_LARGE_FILES,
    'empty_folders': ENABLE_EMPTY_FOLDERS,
    'browser_cache': ENABLE_BROWSER_CACHE,
    'ide_cache': ENABLE_IDE_CACHE,
    'log_files': ENABLE_LOG_FILES,
    'installer_cache': ENABLE_INSTALLER_CACHE,
    'pip_cache': ENABLE_PIP_CACHE,
    'npm_cache': ENABLE_NPM_CACHE,
    'yarn_cache': ENABLE_YARN_CACHE,
    'maven_repo': ENABLE_MAVEN_REPO,
    'gradle_cache': ENABLE_GRADLE_CACHE,
    'conda_pkgs': ENABLE_CONDA_PKGS,
    'jdk_versions': ENABLE_JDK_VERSIONS,
    'thumbnails': ENABLE_THUMBNAILS,
    'error_reports': ENABLE_ERROR_REPORTS,
    'delivery_opt': ENABLE_DELIVERY_OPT,
    'recycle_bin': ENABLE_RECYCLE_BIN,
}
SCAN_ITEMS = []
for item in _BASE_SCAN_ITEMS:
    if ENABLE_MAP.get(item['id'], True):
        SCAN_ITEMS.append(item)
if ENABLE_RECYCLE_BIN:
    SCAN_ITEMS.append({'id': 'recycle_bin', 'name': '回收站', 'risk': 'low'})
if CUSTOM_CACHE_DIRS:
    for idx, p in enumerate(CUSTOM_CACHE_DIRS):
        if p.exists():
            SCAN_ITEMS.append({
                'id': f'custom_{idx}',
                'name': f'自定义缓存 {p.name}',
                'risk': 'low'
            })