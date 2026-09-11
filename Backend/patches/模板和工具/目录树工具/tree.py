import os
import sys
from pathlib import Path

def generate_tree(root_dir, prefix="", exclude_dirs=None, max_depth=None, current_depth=0):
    if exclude_dirs is None:
        exclude_dirs = {'.git', '__pycache__', '.idea', '.vscode', 'node_modules', '.venv', 'venv'}
    
    if max_depth is not None and current_depth >= max_depth:
        return []
    
    root = Path(root_dir)
    if not root.exists() or not root.is_dir():
        return []
    
    items = sorted([p for p in root.iterdir() if p.name not in exclude_dirs], key=lambda x: (not x.is_dir(), x.name.lower()))
    lines = []
    
    for idx, item in enumerate(items):
        is_last = idx == len(items) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{item.name}{'/' if item.is_dir() else ''}")
        
        if item.is_dir():
            extension = "    " if is_last else "│   "
            lines.extend(generate_tree(item, prefix + extension, exclude_dirs, max_depth, current_depth + 1))
    
    return lines

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else input("请输入根目录路径: ").strip()
    root = Path(root)
    
    if not root.exists() or not root.is_dir():
        print("错误: 路径不存在或不是目录")
        sys.exit(1)
    
    print(f"\n{root.name}")
    lines = generate_tree(root)
    for line in lines:
        print(line)
    print()

if __name__ == "__main__":
    main()