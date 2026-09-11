#这是python、yaml转bcs的打包补丁脚本，只收一个python文件和一个与python文件同名的yaml配置文件

import os
import sys
import time
import struct
import hashlib
from pathlib import Path

def build_bcs(py_file, yaml_file, output_file=None, author="Bohh"):
    py_path = Path(py_file)
    yaml_path = Path(yaml_file)

    if not py_path.exists():
        print(f"错误: {py_file} 不存在")
        return False
    if not yaml_path.exists():
        print(f"错误: {yaml_file} 不存在")
        return False

    py_data = py_path.read_bytes()
    yaml_data = yaml_path.read_bytes()
    sha256 = hashlib.sha256(py_data + yaml_data).hexdigest()

    if output_file is None:
        output_file = py_path.stem + ".bcs"

    with open(output_file, 'wb') as f:
        f.write(b'CLSL')
        f.write(struct.pack('B', 2))
        f.write(time.strftime("%Y-%m-%d %H:%M:%S").encode('utf-8'))
        f.write(author.encode('utf-8'))
        f.write(b'\x00')
        f.write(sha256.encode('utf-8'))
        f.write(struct.pack('<I', len(py_data)))
        f.write(struct.pack('<I', len(yaml_data)))
        f.write(py_data)
        f.write(yaml_data)

    print(f"打包完成: {output_file}")
    print(f"  Python: {len(py_data)} 字节")
    print(f"  YAML: {len(yaml_data)} 字节")
    print(f"  作者: {author}")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  SHA256: {sha256}")
    return True

def interactive():
    print("白板补丁打包工具\n")

    author = input("请输入作者名（直接回车默认使用作者大名）: ").strip()
    if not author:
        author = "Bohh"

    basename = input("请输入补丁文件名（不含后缀，补丁俩文件必须同名）: ").strip()
    if not basename:
        print("文件名不能为空！")
        return False

    py_file = basename + ".py"
    yaml_file = basename + ".yaml"

    print()
    print(f"正在打包: {py_file} + {yaml_file}")
    print(f"作者: {author}")
    print()

    return build_bcs(py_file, yaml_file, author=author)

if __name__ == "__main__":
    if len(sys.argv) == 1:
        interactive()
    elif len(sys.argv) >= 3:
        py_file = sys.argv[1]
        yaml_file = sys.argv[2]
        author = sys.argv[3] if len(sys.argv) > 3 else "Bohh"
        build_bcs(py_file, yaml_file, author=author)
    else:
        print("用法:")
        print("  交互式: python py_yaml--bcs_build.py")
        print("  命令行: python py_yaml--bcs_build.py <py文件> <yaml文件> [作者名]")
        sys.exit(1)