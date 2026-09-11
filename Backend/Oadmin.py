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
        input()

    sys.exit(0)
if __name__ == "__main__":
    if not is_admin():
        print("当前未使用管理员权限运行，程序将退出，请右键以管理员身份重新打开")
        input()
        sys.exit(1)
    try:
        from main import main
        main()
    except ImportError as e:
        print(f"启动主程序失败: {e}")
        input()
        sys.exit(1)