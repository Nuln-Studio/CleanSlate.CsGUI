import sys
import ctypes
import subprocess
import os

def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except:
        return False

def run_as_admin():
    if is_admin():
        return
    if getattr(sys, "frozen", False):
        exe = sys.executable
        params = subprocess.list2cmdline(sys.argv[1:])
    else:
        exe = sys.executable
        script = os.path.abspath(__file__)
        params = subprocess.list2cmdline([script, *sys.argv[1:]])
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        exe,
        params,
        None,
        1
    )
    if ret <= 32:
        print("获取管理员权限失败，或用户在 UAC 弹窗里选择了“否”。")
    sys.exit(0)
if __name__ == "__main__":
    run_as_admin()
    try:
        import api
        api.main_entry()
    except ImportError as e:
        print(f"模块导入失败: {e}")
        sys.exit(1)
