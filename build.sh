#!/bin/bash
# Launchpad BPM Controller - macOS .app 빌드
set -e

APP_NAME="Launchpad BPM"

echo "▶ PyInstaller 설치 확인..."
pip3 install pyinstaller --quiet

echo "▶ 빌드 시작: $APP_NAME"
pyinstaller \
  --name "$APP_NAME" \
  --windowed \
  --add-data "templates:templates" \
  --hidden-import engineio.async_drivers.threading \
  --hidden-import flask_socketio \
  --hidden-import mido.backends.rtmidi \
  --hidden-import PySide6.QtWebEngineWidgets \
  --hidden-import PySide6.QtWebEngineCore \
  --collect-submodules PySide6.QtWebEngineWidgets \
  --noconfirm \
  main.py

echo ""
echo "✅ 빌드 완료!"
echo "   앱 위치: $(pwd)/dist/$APP_NAME.app"
echo "   Finder에서 더블클릭으로 실행하세요."
