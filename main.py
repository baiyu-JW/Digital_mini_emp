import subprocess
import sys

if __name__ == "__main__":
    print("=" * 50)
    print("📊 欢迎使用 智能经营周报系统")
    print("正在启动本地服务，请稍候...")
    print("=" * 50)

    subprocess.run([sys.executable, "-m", "streamlit", "run", "src/app.py"])