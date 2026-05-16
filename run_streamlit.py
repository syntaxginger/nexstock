"""รัน Streamlit UI"""
import subprocess, sys, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.run([sys.executable, "-m", "streamlit", "run",
                "streamlit_app/Home.py", "--server.port", "8501"])
