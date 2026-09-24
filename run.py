import os
import sys
import multiprocessing
import threading
import time
import socket
import traceback
import ctypes
import shutil

# Critical for PyInstaller frozen execution on Windows
multiprocessing.freeze_support()

# Ensure the local directory and .venv site-packages are on sys.path if not already active
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

venv_site = os.path.join(base_dir, ".venv", "Lib", "site-packages")
if os.path.isdir(venv_site) and venv_site not in sys.path:
    sys.path.insert(0, venv_site)

# Make CUDA and bundled DLLs discoverable immediately
try:
    from app.transcriber import _add_cuda_dll_directories
    _add_cuda_dll_directories()
except Exception:
    pass

def show_error(title: str, msg: str):
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(0, msg, title, 0x10 | 0x0)
    else:
        print(f"[{title}] {msg}", file=sys.stderr)

def find_available_port(start_port=8000, max_attempts=50):
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port

def wait_for_port(port, host='127.0.0.1', timeout=20.0):
    start_time = time.time()
    while time.time() - start_time < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.3)
    return False

def check_requirements():
    errors = []
    try:
        import psutil
        ram = psutil.virtual_memory().total / (1024 ** 3)
        if ram < 3.5:
            errors.append(f"Low system RAM: {ram:.1f}GB detected. Minimum 4GB recommended.")
    except Exception:
        pass

    if not shutil.which("ffmpeg"):
        errors.append("FFmpeg is not found on system PATH. Video processing will require FFmpeg.")

    if errors:
        msg = "Notice / Requirement Warning:\n\n" + "\n".join(errors) + "\n\nAurum Clipper will still attempt to run."
        if sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(0, msg, "Aurum Clipper Hardware Check", 0x30 | 0x0)

def main():
    try:
        import webview
        import uvicorn
    except ImportError as e:
        show_error("Missing Dependencies", f"Required dependency missing: {e}\nPlease run Install.bat or install requirements.txt.")
        sys.exit(1)

    check_requirements()

    port = find_available_port(8000)

    def start_server():
        try:
            from app.main import app
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
        except Exception as exc:
            show_error("Server Error", f"Backend server crashed on startup:\n{traceback.format_exc()}")

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    if wait_for_port(port):
        try:
            webview.create_window('Aurum Clipper', f'http://127.0.0.1:{port}/', width=1300, height=850, min_size=(1000, 650))
            webview.start()
        except Exception as exc:
            show_error("Window Error", f"Failed to initialize window:\n{traceback.format_exc()}")
            sys.exit(1)
    else:
        show_error("Timeout Error", f"The local backend server did not respond on port {port} within 20 seconds.")
        sys.exit(1)

if __name__ == '__main__':
    main()
