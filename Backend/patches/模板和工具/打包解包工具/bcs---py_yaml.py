import os
import sys
import struct
import hashlib
from pathlib import Path

def extract_bcs(filepath, output_dir=None):
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"错误: {filepath} 不存在")
        return False

    if filepath.suffix.lower() != '.bcs':
        print("错误: 请提供 .bcs 文件")
        return False

    if output_dir is None:
        output_dir = Path.cwd() / 'bcs_extracted' / filepath.stem

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with open(filepath, 'rb') as f:
            magic = f.read(4)
            if magic != b'CLSL':
                print("错误: 不是有效的 bcs 文件 (魔数不匹配)")
                return False

            version = struct.unpack('B', f.read(1))[0]
            if version != 2:
                print(f"错误: 不支持的版本: {version}，请使用最新版打包工具重新打包")
                return False

            time_bytes = f.read(19)
            if len(time_bytes) != 19:
                print("错误: 时间字段长度错误")
                return False
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
                print("错误: SHA256 长度错误")
                return False

            py_len = struct.unpack('<I', f.read(4))[0]
            yaml_len = struct.unpack('<I', f.read(4))[0]
            py_data = f.read(py_len)
            yaml_data = f.read(yaml_len)

            if len(py_data) != py_len:
                print(f"错误: Python 数据不完整 (预期 {py_len}, 实际 {len(py_data)})")
                return False

            calc_hash = hashlib.sha256(py_data + yaml_data).hexdigest()
            if calc_hash != stored_hash:
                print("错误: SHA256 校验失败，文件可能损坏")
                return False

        py_path = output_dir / f"{filepath.stem}.py"
        yaml_path = output_dir / f"{filepath.stem}.yaml"
        py_path.write_bytes(py_data)
        yaml_path.write_bytes(yaml_data)

        print(f"解包完成!")
        print(f"  输出目录: {output_dir}")
        print(f"  Python: {py_path.name} ({len(py_data)} 字节)")
        print(f"  YAML: {yaml_path.name} ({len(yaml_data)} 字节)")
        print(f"  作者: {author}")
        print(f"  打包时间: {pack_time}")
        print(f"  SHA256: 校验通过")
        return True

    except Exception as e:
        print(f"解包失败: {e}")
        return False

def interactive():
    print("白板 .bcs 解包工具\n")

    filepath = input("请输入 .bcs 文件路径: ").strip()
    if not filepath:
        print("路径不能为空")
        return

    filepath = Path(filepath)
    if not filepath.exists():
        print("文件不存在")
        return

    output_dir = input("输出目录（直接回车使用默认）: ").strip()
    if not output_dir:
        output_dir = None

    extract_bcs(filepath, output_dir)

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        if sys.argv[1] in ['-h', '--help']:
            print("用法:")
            print("  交互式: python bcs_extract.py")
            print("  命令行: python bcs_extract.py <bcs文件路径> [输出目录]")
            print("示例: python bcs_extract.py patch.bcs")
            print("     python bcs_extract.py patch.bcs D:/my_patches")
            sys.exit(0)
        filepath = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) >= 3 else None
        extract_bcs(filepath, output_dir)
    else:
        interactive()