"""
메트로놈 타이밍 엔진
- 크로스페이드 없음: 마디(measure) 끝에서 대기 후 즉시 전환
- 오디오는 브라우저 Web Audio API 담당 → vol 값만 콜백으로 전달
"""
import threading
import time

_TS = {
    '4/4': {'n': 4, 'mult': 1.0,      'tags': ['HI', 'LO', 'LO', 'LO']},
    '3/4': {'n': 3, 'mult': 1.0,      'tags': ['HI', 'LO', 'LO']},
    '2/4': {'n': 2, 'mult': 1.0,      'tags': ['HI', 'LO']},
    '6/8': {'n': 6, 'mult': 1.0/3.0,  'tags': ['HI', 'LO', 'LO', 'MID', 'LO', 'LO']},
}


class Metronome:
    def __init__(self):
        self._lock         = threading.Lock()
        self._state        = 'stopped'
        self._muted        = False
        self._fade_dur     = 5.0
        self._stop_evt     = threading.Event()
        self._thread       = None
        self._pending      = None   # {'bpm', 'time_sig', 'on_start'}
        self._fade_stop_ts = None
        self._callback     = None   # fn(status, bpm, beat_index, n, time_sig, vol)

    def set_fade_duration(self, s):    self._fade_dur = float(s)
    def set_state_callback(self, cb): self._callback = cb
    def set_muted(self, m):           self._muted = bool(m)
    def clear_pending(self):
        with self._lock:
            self._pending = None

    @property
    def state(self):
        with self._lock:
            return self._state

    # ── 제어 ──────────────────────────────────────────────
    def start(self, bpm, time_sig='4/4', on_start=None):
        with self._lock:
            playing = self._state != 'stopped'
            if playing:
                # 재생 중 → 마디 끝에 전환 예약, 페이드 취소
                self._pending = {'bpm': float(bpm), 'time_sig': time_sig, 'on_start': on_start}
                self._fade_stop_ts = None
                self._state = 'playing'
                return
            # 정지 상태 → 즉시 시작
            self._state        = 'playing'
            self._fade_stop_ts = None
            self._muted        = False
            self._pending      = None

        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._stop_evt = threading.Event()
        self._thread   = threading.Thread(
            target=self._run, args=(float(bpm), time_sig), daemon=True)
        self._thread.start()

    def fade(self):
        with self._lock:
            if self._state == 'stopped':
                return
            self._state        = 'fading'
            self._fade_stop_ts = time.perf_counter()

    def stop(self):
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        with self._lock:
            self._state = 'stopped'

    # ── 내부 ──────────────────────────────────────────────
    def _notify(self, status, bpm, bi, n, ts, vol=1.0):
        if self._callback:
            self._callback(status, bpm, bi, n, ts, vol)

    def _run(self, bpm, ts_key):
        ts   = _TS.get(ts_key, _TS['4/4'])
        n    = ts['n']
        mult = ts['mult']
        tags = ts['tags']
        bi   = 0
        nxt  = time.perf_counter()

        while not self._stop_evt.is_set():
            now = time.perf_counter()
            with self._lock:
                fst, cur_st = self._fade_stop_ts, self._state

            # 볼륨 계산
            if fst is not None:
                vol = max(0.0, 1.0 - (now - fst) / self._fade_dur)
                if vol <= 0.0:
                    with self._lock:
                        self._state = 'stopped'
                    self._notify('stopped', 0.0, 0, n, ts_key, 0.0)
                    return
            else:
                vol = 1.0

            # 브라우저로 beat 전달 (muted면 vol=0)
            self._notify(cur_st, bpm, bi, n, ts_key, 0.0 if self._muted else vol)

            # 마디 마지막 박자: pending 적용
            pending_cb = None
            if bi == n - 1:
                with self._lock:
                    p = self._pending
                    if p:
                        self._pending = None
                        bpm    = p['bpm']
                        ts_key = p['time_sig']
                        td     = _TS.get(ts_key, _TS['4/4'])
                        n      = td['n']
                        mult   = td['mult']
                        tags   = td['tags']
                        pending_cb = p.get('on_start')
                        bi = -1  # (bi+1) % n → 0 (새 마디 첫 박)

            bi = (bi + 1) % n

            if pending_cb:
                pending_cb()  # 앱 상태 업데이트 (새 곡 활성화)

            # 다음 박자까지 대기
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
        self._notify('stopped', 0.0, 0, n, ts_key, 0.0)
