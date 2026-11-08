import subprocess
import webbrowser
import time
import threading
import sys
import socket


def find_free_port(start_port=8501):
    """自动寻找一个没被占用的端口号"""
    port = start_port
    while port <= 8550:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
        port += 1
    return start_port


target_port = find_free_port()


def open_browser():
    time.sleep(3)
    url = f"http://localhost:{target_port}"
    webbrowser.open(url)


if __name__ == "__main__":
    print("=" * 50)
    print(f"📊 欢迎使用 智能经营周报系统 (即将运行在端口: {target_port})")
    print("正在启动本地服务，浏览器即将自动打开...")
    print("=" * 50)

    threading.Thread(target=open_browser).start()

    subprocess.run([sys.executable, "-m", "streamlit", "run", "src/app.py", "--server.port", str(target_port)])