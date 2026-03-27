#!/usr/bin/env python3
"""
打包脚本 - 用于部署到其他机器
"""
import os
import shutil
import zipfile
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCLUDE_DIRS = ['backend/venv', '__pycache__', '.git']
EXCLUDE_FILES = ['data/oms.db']  # 不含数据库，新机器重新生成

def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_name = f"oms_deploy_{timestamp}.zip"
    zip_path = os.path.join(BASE_DIR, zip_name)

    print("=" * 50)
    print("  OMS - Deployment Packager")
    print("=" * 50)
    print()

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(BASE_DIR):
            # 排除目录
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith('__pycache__')]

            rel_root = os.path.relpath(root, BASE_DIR)
            if rel_root == '.':
                rel_root = ''

            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.join(rel_root, file)

                # 排除文件
                exclude = False
                for ex in EXCLUDE_FILES:
                    if rel_path.replace('\\', '/') == ex:
                        exclude = True
                        break
                if file.endswith('.pyc') or file.endswith('.zip'):
                    exclude = True

                if not exclude:
                    print(f"  Adding: {rel_path}")
                    zf.write(file_path, rel_path)

    print()
    print("=" * 50)
    print(f"  Done! Package created:")
    print(f"  {zip_path}")
    print("=" * 50)
    print()
    print("To deploy on another Windows machine:")
    print("  1. Copy this zip file")
    print("  2. Extract it")
    print("  3. Make sure Python 3.8+ is installed")
    print("  4. Double-click run.bat")
    print()

if __name__ == "__main__":
    main()
