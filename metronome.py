import threading
import time
import numpy as np
import sounddevice as sd

_SR    = 44100
_BLOCK = 256
_CF    = 1.5      # crossfade seconds


def _click(freq, amp, dur=0.025):
    n = int(_SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    return (np.sin(2 * np.pi * freq * t) * np.exp(-t * 130) * amp).astype(np.float32)


HI  = _click(1600, 0.80)   # beat-1 accent
MID = _click(1200, 0.55)   # 6/8 beat-4
LO  = _click(900,  0.38)   # normal

TIME_SIGS = {
    '4/4': {'n': 4, 'mult': 1.0,      'pat': [HI, LO, LO, LO]},
    '3/4': {'n': 3, 'mult': 1.0,      'pat': [HI, LO, LO]},
    '2/4': {'n': 2, 'mult': 1.0,      'pat': [HI, LO]},
    '6/8': {'n': 6, 'mult': 1.0/3.0,  'pat': [HI, LO, LO, MID, LO, LO]},
}


class _Mixer:
    """sounddevice OutputStream 기반 오디오 믹서 (동시 재생 지원)."""

    def __init__(self):
        self._lock   = threading.Lock()
        self._active = []   # [[buf, pos], ...]
        self._stream = sd.OutputStream(
            samplerate=_SR, channels=1, dtype='float32',
            blocksize=_BLOCK, callback=self._cb,
        )
        self._stream.start()

    def _cb(self, outdata, frames, t, status):
        out = np.zeros(frames, dtype=np.float32)
        with self._lock:
            alive = []
            for item in self._active:
                pos = item[1]
                end = min(pos + frames, len(item[0]))
                out[:end - pos] += item[0][pos:end]
                item[1] = end
                if end < len(item[0]):
                    alive.append(item)
            self._active = alive
        np.clip(out, -1.0, 1.0, out=out)
        outdata[:, 0] = out

    def play(self, src: np.ndarray, vol: float = 1.0):
        data = (src * vol).astype(np.float32)
        with self._lock:
            self._active.append([data, 0])

    def close(self):
        self._stream.stop()
        self._stream.close()


class Metronome:
    def __init__(self):
        self._mix      = _Mixer()
        self._lock     = threading.Lock()
        self._state    = 'stopped'
        self._bpm      = 120.0
        self._ts       = '4/4'
        self._muted    = False
        self._fade_dur = 5.0
        self._stop_evt = threading.Event()
        self._thread   = None
        self._ghost_stop = threading.Event()
        self._fade_stop_ts = None
        self._callback = None

    # ── 설정 ──────────────────────────────────────────────
    def set_fade_duration(self, secs: float):
        self._fade_dur = float(secs)

    def set_state_callback(self, cb):
        self._callback = cb

    def set_muted(self, m: bool):
        self._muted = bool(m)

    @property
    def state(self):
        with self._lock:
            return self._state

    # ── 제어 ──────────────────────────────────────────────
    def start(self, bpm: float, time_sig: str = '4/4'):
        with self._lock:
            crossfade = (self._state != 'stopped')
            old_bpm = self._bpm
            old_ts  = self._ts
            self._bpm   = float(bpm)
            self._ts    = time_sig
            self._state = 'playing'
            self._fade_stop_ts = None
            self._muted = False

        # 구 곡 fade-out ghost 스레드
        if crossfade:
            self._ghost_stop.set()
            self._ghost_stop = threading.Event()
            gstop = self._ghost_stop
            threading.Thread(
                target=self._ghost, args=(old_bpm, old_ts, gstop), daemon=True,
            ).start()

        # 기존 메인 스레드 정지
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

        self._stop_evt = threading.Event()
        self._thread = threading.Thread(
            target=self._run, args=(float(bpm), time_sig, crossfade), daemon=True,
        )
        self._thread.start()

    def fade(self):
        """볼륨만 줄여서 정지 (BPM 유지)."""
        with self._lock:
            if self._state == 'stopped':
                return
            self._state = 'fading'
            self._fade_stop_ts = time.perf_counter()

    def stop(self):
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        with self._lock:
            self._state = 'stopped'

    def close(self):
        self.stop()
        self._mix.close()

    # ── 내부 ──────────────────────────────────────────────
    def _notify(self, status: str, bpm: float):
        if self._callback:
            self._callback(status, bpm)

    def _ghost(self, bpm: float, ts_key: str, stop_evt: threading.Event):
        """crossfade: 구 곡 BPM 유지하며 볼륨 0으로 fade-out."""
        ts    = TIME_SIGS.get(ts_key, TIME_SIGS['4/4'])
        start = time.perf_counter()
        bi    = 0
        nxt   = start

        while not stop_evt.is_set():
            elapsed = time.perf_counter() - start
            vol = max(0.0, 1.0 - elapsed / _CF)
            if vol <= 0.0:
                break
            self._mix.play(ts['pat'][bi], vol)
            bi = (bi + 1) % ts['n']
            nxt += 60.0 / bpm * ts['mult']
            rem = nxt - time.perf_counter()
            if rem > 0 and not stop_evt.wait(rem):
                pass  # waited normally

    def _run(self, bpm: float, ts_key: str, fade_in: bool):
        ts   = TIME_SIGS.get(ts_key, TIME_SIGS['4/4'])
        n    = ts['n']
        mult = ts['mult']
        pat  = ts['pat']

        fi_start = time.perf_counter() if fade_in else None
        bi  = 0
        nxt = time.perf_counter()

        while not self._stop_evt.is_set():
            now = time.perf_counter()

            # ── 볼륨 계산 ────────────────────────────────
            with self._lock:
                fst       = self._fade_stop_ts
                cur_state = self._state

            if fst is not None:
                vol = max(0.0, 1.0 - (now - fst) / self._fade_dur)
                if vol <= 0.0:
                    with self._lock:
                        self._state = 'stopped'
                    self._notify('stopped', 0.0)
                    return
            elif fi_start is not None:
                elapsed = now - fi_start
                vol = min(1.0, elapsed / _CF)
                if elapsed >= _CF:
                    fi_start = None
            else:
                vol = 1.0

            # ── 클릭 재생 ────────────────────────────────
            if not self._muted:
                self._mix.play(pat[bi], vol)

            self._notify(cur_state, bpm)
            bi = (bi + 1) % n

            # ── 다음 비트 대기 ───────────────────────────
            nxt += 60.0 / bpm * mult
            while True:
                rem = nxt - time.perf_counter()
                if rem <= 0:
                    nxt = time.perf_counter()
                    break
                if self._stop_evt.wait(min(0.002, rem)):
                    return

        with self._lock:
            if self._state != 'stopped':
                self._state = 'stopped'
        self._notify('stopped', 0.0)
