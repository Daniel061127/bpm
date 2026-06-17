import platform
import subprocess
import time
import mido

# PyInstaller 번들 환경에서 백엔드 자동 탐색 실패 방지
try:
    mido.set_backend('mido.backends.rtmidi')
except Exception:
    pass

# Launchpad Mini MK3 Programmer Mode SysEx
_SYSEX_PROGRAMMER = [0x00, 0x20, 0x29, 0x02, 0x0D, 0x00, 0x7F]

# macOS: "Launchpad Mini MK3 LPMiniMK3 MIDI Out"
# Windows: "LPMiniMK3 MIDI 0" 또는 "Launchpad Mini MK3 0"
_DEVICE_NAMES = ["Launchpad Mini MK3", "LPMiniMK3", "Launchpad"]
_DEVICE_NAME  = "Launchpad Mini MK3"


class Launchpad:
    def __init__(self):
        self._inport        = None
        self._outport       = None
        self._callback      = None
        self._on_disconnect = None
        self.connected      = False

    def _find_port(self, ports):
        for dev in _DEVICE_NAMES:
            matches = [p for p in ports if dev in p]
            if not matches:
                continue
            # DAW 포트보다 MIDI 포트 우선
            midi = [p for p in matches if 'MIDI' in p]
            if midi:
                return midi[0]
            non_daw = [p for p in matches if 'DAW' not in p]
            if non_daw:
                return non_daw[0]
            return matches[-1]
        return None

    def is_available(self):
        """장치 실물 존재 여부 확인 (macOS: ioreg USB 체크, Windows/기타: mido 포트 목록)"""
        if platform.system() == 'Darwin':
            try:
                r = subprocess.run(
                    ['ioreg', '-r', '-c', 'IOUSBHostDevice'],
                    capture_output=True, text=True, timeout=2
                )
                return _DEVICE_NAME in r.stdout
            except Exception:
                pass
        elif platform.system() == 'Windows':
            try:
                return bool(self._find_port(mido.get_input_names()))
            except Exception:
                return False
        return bool(self._find_port(mido.get_input_names()))

    def _handle_msg(self, msg):
        if self.connected and msg.type in ('note_on', 'note_off'):
            # note_off 또는 velocity=0인 note_on은 무시 (버튼 릴리즈)
            if msg.type == 'note_on' and msg.velocity > 0:
                if self._callback:
                    self._callback(msg.note)

    def _send_programmer_mode(self):
        """SysEx 프로그래머 모드 전환 — 3회까지 재시도"""
        for attempt in range(3):
            try:
                time.sleep(0.05 * (attempt + 1))  # 포트 안정화 대기
                self._outport.send(mido.Message('sysex', data=_SYSEX_PROGRAMMER))
                return True
            except Exception:
                pass
        return False

    def connect(self):
        in_ports  = mido.get_input_names()
        out_ports = mido.get_output_names()
        in_name   = self._find_port(in_ports)
        out_name  = self._find_port(out_ports)

        if not in_name:
            raise RuntimeError(
                f"'{_DEVICE_NAME}' 를 찾을 수 없습니다.\n"
                f"연결된 입력 포트: {in_ports}"
            )
        if not out_name:
            raise RuntimeError(
                f"'{_DEVICE_NAME}' 출력 포트를 찾을 수 없습니다.\n"
                f"연결된 출력 포트: {out_ports}"
            )

        self._inport  = mido.open_input(in_name, callback=self._handle_msg)
        self._outport = mido.open_output(out_name)
        self.connected = True

        # 포트 열린 후 SysEx 전송 (프로그래머 모드)
        self._send_programmer_mode()

        return in_name, out_name

    def resend_programmer_mode(self):
        """외부에서 프로그래머 모드 재전송 (재연결/복구 시 사용)"""
        if self.connected and self._outport:
            self._send_programmer_mode()

    def set_callback(self, cb):
        self._callback = cb

    def set_disconnect_callback(self, cb):
        self._on_disconnect = cb

    def start(self):
        return self.connect()

    def stop(self):
        self.connected = False
        try:
            if self._inport:
                self._inport.close()
                self._inport = None
        except Exception:
            pass
        try:
            if self._outport:
                self._outport.close()
                self._outport = None
        except Exception:
            pass

    def set_led(self, note, color):
        if not self.connected or not self._outport:
            return
        try:
            self._outport.send(
                mido.Message('note_on', channel=0, note=note, velocity=color)
            )
        except Exception:
            self.connected = False

    def clear(self):
        notes = [r * 10 + c for r in range(1, 9) for c in range(1, 9)]
        notes += [19, 29, 39, 49, 59, 69, 79, 89]
        for note in notes:
            self.set_led(note, 0)
