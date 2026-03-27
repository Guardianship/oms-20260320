#!/usr/bin/env python3
"""
OMS - Simple Startup Script
"""
import os
import sys
import subprocess
import platform

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
REQUIREMENTS = os.path.join(BACKEND_DIR, "requirements.txt")
VENV_DIR = os.path.join(BACKEND_DIR, "venv")


def print_banner():
    print("=" * 40)
    print("   OMS - Operation Management System")
    print("=" * 40)
    print()


def check_python():
    print("[1/5] Checking Python...")
    print(f"    Python version: {sys.version}")
    if sys.version_info < (3, 8):
        print("    ERROR: Python 3.8+ is required!")
        return False
    print("    OK")
    print()
    return True


def is_venv_valid():
    """检查虚拟环境是否有效（路径匹配）"""
    if not os.path.exists(VENV_DIR):
        return False
    # 检查 pyvenv.cfg 是否存在
    pyvenv_cfg = os.path.join(VENV_DIR, "pyvenv.cfg")
    if not os.path.exists(pyvenv_cfg):
        return False
    # 检查 python 可执行文件是否存在
    exe_path = get_python_path()
    if not os.path.exists(exe_path):
        return False
    return True


def create_venv():
    print("[2/5] Checking virtual environment...")
    if os.path.exists(VENV_DIR) and not is_venv_valid():
        print(
            "    Virtual environment is invalid (path changed), recreating...")
        import shutil
        shutil.rmtree(VENV_DIR)

    if not os.path.exists(VENV_DIR):
        print("    Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR],
                              cwd=BACKEND_DIR)
        print("    OK")
    else:
        print("    Already exists")
    print()
    return True


def get_pip_path():
    if platform.system() == "Windows":
        return os.path.join(VENV_DIR, "Scripts", "pip.exe")
    return os.path.join(VENV_DIR, "bin", "pip")


def get_python_path():
    if platform.system() == "Windows":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def install_deps():
    print("[3/5] Installing dependencies...")
    pip_path = get_pip_path()
    subprocess.check_call([
        pip_path, "install", "-r", REQUIREMENTS, "-i",
        "https://pypi.tuna.tsinghua.edu.cn/simple"
    ])
    print("    OK")
    print()
    return True


def start_server():
    print("[4/5] Starting server...")
    print()
    print("=" * 40)
    print("  Server is starting!")
    print()
    print("  Open your browser and visit:")
    print("  http://localhost:8000")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 40)
    print()

    python_path = get_python_path()
    os.chdir(BACKEND_DIR)
    subprocess.check_call([
        python_path, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0",
        "--port", "8000"
    ])


def main():
    try:
        print_banner()
        if not check_python():
            input("Press Enter to exit...")
            return 1
        if not create_venv():
            input("Press Enter to exit...")
            return 1
        if not install_deps():
            input("Press Enter to exit...")
            return 1
        start_server()
    except KeyboardInterrupt:
        print()
        print("Server stopped.")
    except Exception as e:
        print()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        print()
        input("Press Enter to exit...")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
