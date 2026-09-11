import sys
import shutil
import importlib.util
import time
import struct
import threading
from pathlib import Path
from scanner import get_all_scans
from cleaner import run_cleaner, CLEAN_MAP
from config import AGGRESSIVE_MODE_ENABLED, ENABLE_PATCH, PATCH_DIR, BACKUP_DIR, BACKUP_RETENTION_DAYS, EMERGENCY_MODE, BASE_DIR, CHECK_UPDATE

class AppState:
    data = {}

VERSION_NUM = "正式版v1.0.4"  #别忘了改这个！！！！！！！！！！！！！！！！！！
VERSION_CODE = 1004   #别忘了改这个！！！！！！！！！！！！！！！！！！
TEMP_PATCH_DIR = BASE_DIR / 'temp_patches'
PATCH_RETENTION_DAYS = 30
_patch_scans = []
_patch_ids = set()



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

def main():
    clean_backup_files()
    clean_temp_patches()
    if CHECK_UPDATE:
        stop = spinner("正在检查更新")
        New_Version()
        stop()
    print(f"当前客户端版本：{VERSION_NUM}")
    print("当前版本适用于 Windows 10 64 位 及更高版本(不支持32位系统)")
    print("制作团队：零阑工坊 (Nuln Studio)")
    input("按下回车继续...")
    if EMERGENCY_MODE:
        print("\n[警告] C盘剩余空间不足2GB，自动进入降级模式：")
        print("  - 跳过高风险清理项（还原点、WinSxS、JDK等）")
        print("  - 禁用备份，避免占用C盘空间")
        print("  - 仅清理安全的临时文件和缓存\n")
    total_gb, free_gb, used_gb = get_disk_info()
    bfree_gb = free_gb
    progerss_str, progerss = progress_disk(total_gb, used_gb)
    print(f"C: 总 {total_gb:.2f} GB, 已用 {used_gb:.2f} GB, 剩余 {free_gb:.2f} GB")
    print(progerss_str, progerss)

    stop_spin2 = spinner("正在扫描磁盘，请稍候")
    AppState.data = get_all_scans()
    stop_spin2()

    if ENABLE_PATCH:
        load_patches_from_dir()
    for func in _patch_scans:
        try:
            result = func()
            if result:
                AppState.data[result.get('id')] = result
        except Exception:
            pass
    while True:
        id_map = display_results(AppState.data)
        safe_total = 0.0
        all_total = 0.0
        for item_id, info in AppState.data.items():
            size = info.get('size_gb', 0)
            risk = info.get('risk', 'low')
            all_total += size
            if risk in ('low', 'medium'):
                safe_total += size
        print(f"\n安全模式预计释放: {safe_total:.2f} GB | 激进模式(配置文件中开启激进选项才可慎用)预计释放: {all_total:.2f} GB")
        print("\n操作选项:")
        print("  1. 手动选择要清理的项")
        if AGGRESSIVE_MODE_ENABLED:
            print("  2. 选择一键清理模式 (安全 / 激进)")
        else:
            print("  2. 安全模式一键清理（清理低风险 + 中风险，中风险自动备份）")
        print("  3. 重新扫描")
        print("  4. 退出")
        if ENABLE_PATCH:
            print("  5. 加载补丁")
        choice_prompt = "请选择 (1/2/3/4" + ("/5" if ENABLE_PATCH else "") + "): "
        choice = input(choice_prompt).strip()
        if choice == '1':
            print("\n手动选择清理项:")
            print("  1. 选择要删除的项 (输入序号，多个用逗号或空格分隔)")
            print("  2. 选择不删除的项 (输入序号，其余将全被删除)")
            print("  3. 全选")
            print("  4. 返回")
            sub = input("请选择 (1/2/3/4): ").strip()
            selected_ids = []
            if sub == '1':
                idx_input = input("请输入要删除的序号 (如: 1,3,5 或 1 3 5): ").strip()
                if not idx_input:
                    print("未输入任何序号，返回。")
                    continue
                idx_list = []
                for part in idx_input.replace(',', ' ').split():
                    if part.isdigit():
                        idx_list.append(int(part))
                selected_ids = [id_map[i] for i in idx_list if i in id_map]
                if not selected_ids:
                    print("没有有效序号，返回。")
                    continue
            elif sub == '2':
                idx_input = input("请输入不删除的序号 (如: 1,3,5 或 1 3 5): ").strip()
                if not idx_input:
                    print("未输入任何序号，将删除全部项。")
                    selected_ids = list(id_map.values())
                else:
                    exclude_set = set()
                    for part in idx_input.replace(',', ' ').split():
                        if part.isdigit():
                            exclude_set.add(int(part))
                    selected_ids = [id_map[i] for i in id_map if i not in exclude_set]
                if not selected_ids:
                    print("没有可删除的项，返回。")
                    continue
            elif sub == '3':
                selected_ids = list(id_map.values())
            else:
                continue
            print("\n即将清理以下项:")
            for item_id in selected_ids:
                info = AppState.data.get(item_id, {})
                print(f"  - {info.get('name', item_id)} ({info.get('size_gb', 0):.2f} GB)")
            confirm = input("确认清理？(y/N): ").strip().lower()
            if confirm != 'y':
                print("已取消。")
                continue
            print("\n开始清理...")
            success_count = 0
            fail_count = 0
            total_freed = 0.0
            total_items = len(selected_ids)
            for item_idx, item_id in enumerate(selected_ids, 1):
                print(f"\n[清理项 {item_idx}/{total_items}] 正在处理: {AppState.data.get(item_id, {}).get('name', item_id)}")
                if item_id not in AppState.data:
                    print(f"跳过未知项: {item_id}")
                    continue
                risk = AppState.data[item_id].get('risk', 'low')
                if risk == 'high':
                    sec = input(f"项 '{item_id}' 风险为高，是否继续？(y/N): ").strip().lower()
                    if sec != 'y':
                        print(f"跳过 {item_id}")
                        continue
                result = run_cleaner(item_id)
                if result['success']:
                    print(f"  [成功] {item_id} - {result['message']}")
                    success_count += 1
                    total_freed += result.get('freed_gb', 0.0)
                else:
                    print(f"  [失败] {item_id} - {result['message']}")
                    fail_count += 1
            show_clean_result(success_count, fail_count, total_freed)
            input("按回车键继续...")
            print("重新扫描...")
            AppState.data = get_all_scans()
            for func in _patch_scans:
                try:
                    result = func()
                    if result:
                        AppState.data[result.get('id')] = result
                except Exception:
                    pass
        elif choice == '2':
            if AGGRESSIVE_MODE_ENABLED:
                mode_choice = input("选择模式: 1-安全 (清理低+中风险，中风险备份)  2-激进 (清理全部，中高风险备份): ").strip()
                if mode_choice not in ['1', '2']:
                    print("无效选项")
                    continue
                is_aggressive = (mode_choice == '2')
            else:
                is_aggressive = False
            selected_ids = []
            for item_id, info in AppState.data.items():
                size = info.get('size_gb', 0)
                if size < 0.01:
                    continue
                risk = info.get('risk', 'low')
                if is_aggressive:
                    selected_ids.append(item_id)
                else:
                    if risk in ('low', 'medium'):
                        selected_ids.append(item_id)
            if not selected_ids:
                print("没有项可清理。")
                continue
            print("\n将清理以下项:")
            for i in selected_ids:
                risk_disp = AppState.data[i].get('risk', 'low')
                risk_cn = {'low': '低', 'medium': '中', 'high': '高'}.get(risk_disp, '低')
                print(f"  - {AppState.data[i].get('name', i)} ({AppState.data[i].get('size_gb', 0):.2f} GB, 风险{risk_cn})")
            confirm = input("确认清理？(y/N): ").strip().lower()
            if confirm != 'y':
                print("取消。")
                continue
            print("开始清理...")
            print("清理时间较长，请耐心等待，不要关闭这个窗口")
            print("清理时预期可能与结果不符（例如日志文件只删除）")
            success_count = 0
            fail_count = 0
            total_freed = 0.0
            total_items = len(selected_ids)
            for item_idx, item_id in enumerate(selected_ids, 1):
                print(f"\n[清理项 {item_idx}/{total_items}] 正在处理: {AppState.data.get(item_id, {}).get('name', item_id)}")
                risk = AppState.data[item_id].get('risk', 'low')
                if risk == 'high':
                    sec = input(f"项 '{item_id}' 风险为高，仍继续？(y/N): ").strip().lower()
                    if sec != 'y':
                        print(f"跳过 {item_id}")
                        continue
                result = run_cleaner(item_id)
                if result['success']:
                    print(f"  [成功] {item_id} - {result['message']}")
                    success_count += 1
                    total_freed += result.get('freed_gb', 0.0)
                else:
                    print(f"  [失败] {item_id} - {result['message']}")
                    fail_count += 1
            show_clean_result(success_count, fail_count, total_freed)
            input("按回车键继续...")
            print("重新扫描...")
            AppState.data = get_all_scans()
            for func in _patch_scans:
                try:
                    result = func()
                    if result:
                        AppState.data[result.get('id')] = result
                except Exception:
                    pass
        elif choice == '3':
            print("重新扫描中...")
            AppState.data = get_all_scans()
            for func in _patch_scans:
                try:
                    result = func()
                    if result:
                        AppState.data[result.get('id')] = result
                except Exception:
                    pass
            print("扫描完成。")
            input("按回车键继续...")
        elif choice == '4':
            print("感谢使用，再见。")
            sys.exit(0)
        elif choice == '5' and ENABLE_PATCH:
            patch_path = input("请输入补丁文件路径: ").strip()
            if not patch_path:
                print("路径为空，取消加载。")
                continue
            if not Path(patch_path).exists():
                print("文件不存在。")
                continue
            patch_info = load_patch_file(patch_path)
            if patch_info is None:
                print("补丁加载失败。")
                continue
            pid = patch_info['id']
            if pid in _patch_ids:
                print(f"补丁 '{pid}' 已加载，无需重复。")
                input("按回车键继续...")
                continue
            src_file = Path(patch_path)
            PATCH_DIR.mkdir(parents=True, exist_ok=True)
            dest_file = PATCH_DIR / src_file.name
            if not dest_file.exists():
                shutil.copy2(src_file, dest_file)
                src_yaml = src_file.with_suffix('.yaml')
                if src_yaml.exists():
                    shutil.copy2(src_yaml, PATCH_DIR / src_yaml.name)
            CLEAN_MAP[pid] = patch_info['clean']
            _patch_scans.append(patch_info['scan'])
            _patch_ids.add(pid)
            try:
                result = patch_info['scan']()
                if result:
                    AppState.data[pid] = result
            except Exception as e:
                print(f"补丁扫描执行失败: {e}")
            print(f"集成补丁 '{patch_info['name']}' 加载成功！")
            input("按回车键继续...")
        else:
            print("无效选项，请重新选择。")
            input("按回车键继续...")
