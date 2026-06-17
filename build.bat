@echo off
REM Launchpad BPM Controller - Windows .exe 빌드

set APP_NAME=Launchpad BPM

echo ▶ 패키지 설치 확인...
pip install flask flask-socketio mido python-rtmidi PySide6 pyinstaller

echo ▶ 빌드 시작: %APP_NAME%
pyinstaller ^
  --name "%APP_NAME%" ^
  --windowed ^
  --add-data "templates;templates" ^
  --hidden-import engineio.async_drivers.threading ^
  --hidden-import flask_socketio ^
  --hidden-import mido.backends.rtmidi ^
  --hidden-import PySide6.QtWebEngineWidgets ^
  --hidden-import PySide6.QtWebEngineCore ^
  --noconfirm ^
  main.py

echo.
echo ✅ 빌드 완료!
echo    앱 위치: dist\%APP_NAME%.exe
pause
