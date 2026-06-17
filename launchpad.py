import platform
import subprocess
import threading
import time
import mido

try:
    mido.set_backend('mido.backends.rtmidi')
except Exception:
    pass

_SYSEX_PROGRAMMER = [0x00, 0x20, 0x29, 0x02, 0x0D, 0x00, 0x7F]

_DEVICE_NAMES = ["Launchpad Mini MK3", "LPMiniMK3", "Launchpad"]
_DEVICE_NAME  = "Launchpad Mini MK3"

# 최근 수신 MIDI 메시지 로그 (진단용)
midi_log = []
_LOG_MAX = 30


class Launchpad:
    def __init__(self):
        self._inport   = None
        self._outport  = None
        self._callback = None
        self.connected = False
        self.in_name   = None
        self.out_name  = None
        self.sysex_ok  = False

    def _find_port(self, ports):
        for dev in _DEVICE_NAMES:
            matches = [p for p in ports if dev in p]
            if not matches:
                continue
            midi = [p for p in matches if 'MIDI' in p]
            if midi:
                return midi[0]
            non_daw = [p for p in matches if 'DAW' not in p]
            return non_daw[0] if non_daw else matches[-1]
        return None

    def is_available(self):
        if platform.system() == 'Darwin':
            try:
                r = subprocess.run(
                    ['ioreg', '-r', '-c', 'IOUSBHostDevice'],
                    capture_output=True, text=True, timeout=2
                )
                return _DEVICE_NAME in r.stdout
            except Exception:
                pass
        try:
            return bool(self._find_port(mido.get_input_names()))
        except Exception:
            return False

    def _handle_msg(self, msg):
        global midi_log
        entry = f"{msg.type} note={getattr(msg,'note','?')} vel={getattr(msg,'velocity','?')} ch={getattr(msg,'channel','?')}"
        midi_log = ([entry] + midi_log)[:_LOG_MAX]
        if self.connected and self._callback:
            if msg.type == 'note_on' and msg.velocity > 0:
                self._callback(msg.note)

    def _send_programmer_mode(self):
        """포트 오픈 후 백그라운드에서 SysEx를 반복 전송 (최대 10초)"""
        def _retry():
            deadline = time.time() + 10.0
            interval = 0.2
            while time.time() < deadline and self.connected:
                try:
                    self._outport.send(mido.Message('sysex', data=_SYSEX_PROGRAMMER))
                    self.sysex_ok = True
                    return
                except Exception:
                    pass
                time.sleep(interval)
                interval = min(interval * 1.5, 1.0)
        threading.Thread(target=_retry, daemon=True).start()

    def connect(self):
        in_ports  = mido.get_input_names()
        out_ports = mido.get_output_names()
        in_name   = self._find_port(in_ports)
        out_name  = self._find_port(out_ports)

        if not in_name:
            raise RuntimeError(f"포트 없음. 입력: {in_ports}")
        if not out_name:
            raise RuntimeError(f"출력 포트 없음. 출력: {out_ports}")

        self._inport  = mido.open_input(in_name, callback=self._handle_msg)
        self._outport = mido.open_output(out_name)
        self.connected = True
        self.in_name   = in_name
        self.out_name  = out_name
        self.sysex_ok  = False
        self._send_programmer_mode()
        return in_name, out_name

    def set_callback(self, cb):
        self._callback = cb

    def start(self):
        return self.connect()

    def stop(self):
        self.connected = False
        self.sysex_ok  = False
        for port in (self._inport, self._outport):
            try:
                if port:
                    port.close()
            except Exception:
                pass
        self._inport = self._outport = None

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
        for r in range(1, 9):
            for c in range(1, 9):
                self.set_led(r * 10 + c, 0)
        for note in [19, 29, 39, 49, 59, 69, 79, 89]:
            self.set_led(note, 0)
