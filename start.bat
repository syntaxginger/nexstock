@echo off
echo Starting NexStock...

start "FastAPI" cmd /k "cd /d D:\project with claude\NexStock && python run.py"
timeout /t 2 /nobreak >nul

start "Streamlit" cmd /k "cd /d D:\project with claude\NexStock && python run_streamlit.py"
timeout /t 2 /nobreak >nul

start "ngrok" cmd /k "cd /d D:\project with claude\NexStock && ngrok.exe http 8000"

echo.
echo ========================================
echo  NexStock started!
echo  FastAPI   : http://localhost:8000
echo  Streamlit : http://localhost:8501
echo  API Docs  : http://localhost:8000/docs
echo  ngrok     : http://localhost:4040
echo ========================================
pause
