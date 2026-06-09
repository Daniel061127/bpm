import threading
import mido

# Launchpad Mini MK3 Programmer 모드 진입 SysEx
_SYSEX_PROGRAMMER = [0x00, 0x20, 0x29, 0x02, 0x0D, 0x00, 0x7F]
_DEVICE_NAME = "Launchpad Mini MK3"


class Launchpad:
    def __init__(self):
        self._inport = None
        self._outport = None
        self._callback = None
        self._running = False
        self._thread = None
        self.connected = False

    def _find_port(self, ports):
        matches = [p for p in ports if _DEVICE_NAME in p]
        if not matches:
            return None
        # MIDI 2 포트 (인덱스 1) = Programmer API 전용
        return matches[1] if len(matches) >= 2 else matches[0]

    def connect(self):
        in_name = self._find_port(mido.get_input_names())
        out_name = self._find_port(mido.get_output_names())

        if not in_name:
            available = mido.get_input_names()
            raise RuntimeError(
                f"'{_DEVICE_NAME}' 를 찾을 수 없습니다.\n"
                f"연결된 포트: {available}"
            )

        self._inport = mido.open_input(in_name)
        self._outport = mido.open_output(out_name)

        # Programmer 모드 진입
        self._outport.send(mido.Message('sysex', data=_SYSEX_PROGRAMMER))
        self.connected = True
        return in_name, out_name

    def set_callback(self, cb):
        self._callback = cb

    def start(self):
        names = self.connect()
        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()
        return names

    def stop(self):
        self._running = False
        try:
            if self._inport and not self._inport.closed:
                self._inport.close()
        except Exception:
            pass
        try:
            if self._outport and not self._outport.closed:
                self._outport.close()
        except Exception:
            pass

    def set_led(self, note, color):
        if not self.connected:
            return
        try:
            self._outport.send(
                mido.Message('note_on', channel=0, note=note, velocity=color)
            )
        except Exception:
            pass

    def clear(self):
        notes = [r * 10 + c for r in range(1, 9) for c in range(1, 9)]
        notes += [19, 29, 39, 49, 59, 69, 79, 89]
        for note in notes:
            self.set_led(note, 0)

    def _listen(self):
        try:
            for msg in self._inport:
                if not self._running:
                    break
                if msg.type == 'note_on' and msg.velocity > 0:
                    if self._callback:
                        self._callback(msg.note)
        except Exception:
            pass
