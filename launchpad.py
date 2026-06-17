import platform
import subprocess
import mido

_SYSEX_PROGRAMMER = [0x00, 0x20, 0x29, 0x02, 0x0D, 0x00, 0x7F]
_DEVICE_NAME = "Launchpad Mini MK3"


class Launchpad:
    def __init__(self):
        self._inport        = None
        self._outport       = None
        self._callback      = None
        self._on_disconnect = None
        self.connected      = False

    def _find_port(self, ports):
        matches = [p for p in ports if _DEVICE_NAME in p]
        if not matches:
            return None
        return matches[1] if len(matches) >= 2 else matches[0]

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
            # Windows는 CoreMIDI 오프라인 잔류 문제 없음 → mido 포트 목록 직접 사용
            try:
                return bool(self._find_port(mido.get_input_names()))
            except Exception:
                return False
        return bool(self._find_port(mido.get_input_names()))

    def _handle_msg(self, msg):
        if self.connected and msg.type == 'note_on' and msg.velocity > 0:
            if self._callback:
                self._callback(msg.note)

    def connect(self):
        in_name  = self._find_port(mido.get_input_names())
        out_name = self._find_port(mido.get_output_names())
        if not in_name:
            raise RuntimeError(
                f"'{_DEVICE_NAME}' 를 찾을 수 없습니다.\n"
                f"연결된 포트: {mido.get_input_names()}"
            )
        self._inport  = mido.open_input(in_name, callback=self._handle_msg)
        self._outport = mido.open_output(out_name)
        self._outport.send(mido.Message('sysex', data=_SYSEX_PROGRAMMER))
        self.connected = True
        return in_name, out_name

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
