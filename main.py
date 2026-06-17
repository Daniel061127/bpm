#!/usr/bin/env python3
"""
Launchpad BPM Controller - GUI 런처
python3 main.py 로 실행하면 독립 창으로 뜸
"""
import logging
import sys
import threading
import time

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings

from app import app, socketio, launchpad, state, init_leds

PORT = 5001

logging.getLogger('werkzeug').setLevel(logging.ERROR)


def _start_server():
    socketio.run(app, host='127.0.0.1', port=PORT,
                 debug=False, allow_unsafe_werkzeug=True)


class BPMWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Launchpad BPM Controller')
        self.resize(860, 640)
        self.setMinimumSize(700, 500)

        self._view = QWebEngineView()
        self._view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, False)
        self._view.load(QUrl(f'http://127.0.0.1:{PORT}'))
        self.setCentralWidget(self._view)

    def closeEvent(self, event):
        launchpad.stop()
        event.accept()


if __name__ == '__main__':
    # 런치패드 연결 (reconnect loop이 실패 시 재시도)
    try:
        launchpad.start()
        state['launchpad'] = True
        init_leds()
    except Exception:
        pass

    # Flask 서버 백그라운드 실행
    threading.Thread(target=_start_server, daemon=True).start()
    time.sleep(1.0)

    qt = QApplication(sys.argv)
    qt.setApplicationName('Launchpad BPM Controller')
    win = BPMWindow()
    win.show()
    sys.exit(qt.exec())
