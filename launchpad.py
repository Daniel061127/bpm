import platform
import subprocess
import time
import mido

try:
    mido.set_backend('mido.backends.rtmidi')
except Exception:
    pass

_SYSEX_PROGRAMMER = [0x00, 0x20, 0x29, 0x02, 0x0D, 0x00, 0x7F]

# macOS: "Launchpad Mini MK3 LPMiniMK3 MIDI Out"
# Windows: "LPMiniMK3 MIDI 0"
_DEVICE_NAMES = ["Launchpad Mini MK3", "LPMiniMK3", "Launchpad"]
_DEVICE_NAME  = "Launchpad Mini MK3"


class Launchpad:
    def __init__(self):
        self._inport   = None
        self._outport  = None
        self._callback = None
        self.connected = False

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
        if self.connected and self._callback:
            if msg.type == 'note_on' and msg.velocity > 0:
                self._callback(msg.note)

    def _send_programmer_mode(self):
        for attempt in range(3):
            try:
                time.sleep(0.05 * (attempt + 1))
                self._outport.send(mido.Message('sysex', data=_SYSEX_PROGRAMMER))
                return
            except Exception:
                pass

    def connect(self):
        in_name  = self._find_port(mido.get_input_names())
        out_name = self._find_port(mido.get_output_names())
        if not in_name:
            raise RuntimeError(
                f"'{_DEVICE_NAME}' 를 찾을 수 없습니다. "
                f"연결된 포트: {mido.get_input_names()}"
            )
        if not out_name:
            raise RuntimeError(
                f"'{_DEVICE_NAME}' 출력 포트를 찾을 수 없습니다. "
                f"연결된 포트: {mido.get_output_names()}"
            )
        self._inport  = mido.open_input(in_name, callback=self._handle_msg)
        self._outport = mido.open_output(out_name)
        self.connected = True
        self._send_programmer_mode()
        return in_name, out_name

    def set_callback(self, cb):
        self._callback = cb

    def start(self):
        return self.connect()

    def stop(self):
        self.connected = False
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
