@echo off
chcp 65001 >nul
title Launchpad BPM Controller

echo ========================================
echo   Launchpad BPM Controller
echo   made by Kangyun Choi / ariseworship.kr
echo ========================================
echo.

:: Python 설치 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo.
    echo Python 3.11 이상을 설치해 주세요:
    echo https://www.python.org/downloads/
    echo.
    echo 설치 시 "Add Python to PATH" 반드시 체크!
    pause
    exit /b 1
)

echo Python 확인 완료.
echo.

:: 패키지 설치 (처음 한 번만 오래 걸림)
echo 필요한 패키지를 확인합니다...
pip install flask flask-socketio mido python-rtmidi PySide6 --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [오류] 패키지 설치 실패. 인터넷 연결을 확인해 주세요.
    pause
    exit /b 1
)

echo.
echo 앱을 시작합니다...
echo (창을 닫으면 종료됩니다)
echo.

python main.py

if errorlevel 1 (
    echo.
    echo [오류] 앱 실행 중 문제가 발생했습니다.
    pause
)
