#!/usr/bin/env python3
"""
Launchpad BPM Controller
  설치: pip install -r requirements.txt
        brew install portaudio   (macOS, sounddevice 의존성)

  사용법:
    python main.py

  패드 배치 (config.py 에서 수정):
    상단 행 (81~88) → 각 곡 실행
    패드 89 (오른쪽 열 맨 위) → BPM 페이드 스탑
"""
import tkinter as tk

from config import (
    SONGS, PAD_TO_SONG,
    FADE_PAD, FADE_DURATION, MIN_FADE_BPM,
    LED_OFF, LED_GREEN, LED_ORANGE, LED_BLUE,
)
from metronome import Metronome
from launchpad import Launchpad
from gui import BpmGui


def main():
    root = tk.Tk()

    metronome = Metronome()
    metronome.set_fade_params(FADE_DURATION, MIN_FADE_BPM)

    launchpad = Launchpad()
    gui = BpmGui(root, SONGS)

    # 공유 상태
    state = {"song": None, "bpm": 0.0, "status": "stopped"}

    def refresh():
        gui.update(state["status"], state["song"], state["bpm"])

    # ── 메트로놈 → GUI (메트로놈 스레드에서 호출) ────────────
    def on_metro(metro_status, metro_bpm):
        state["bpm"] = metro_bpm
        state["status"] = metro_status

        if metro_status == "stopped":
            state["song"] = None
            for s in SONGS:
                launchpad.set_led(s["pad"], LED_BLUE)
            launchpad.set_led(FADE_PAD, LED_OFF)

        refresh()

    metronome.set_state_callback(on_metro)

    # ── 런치패드 패드 입력 → 동작 ────────────────────────────
    def on_pad(note):
        if note in PAD_TO_SONG:
            song = PAD_TO_SONG[note]
            state["song"] = song
            state["bpm"]  = song["bpm"]
            state["status"] = "playing"

            # LED: 선택 곡 → 초록, 나머지 → 파랑, 페이드 패드 → 주황
            for s in SONGS:
                color = LED_GREEN if s["pad"] == note else LED_BLUE
                launchpad.set_led(s["pad"], color)
            launchpad.set_led(FADE_PAD, LED_ORANGE)

            metronome.start(song["bpm"])
            refresh()

        elif note == FADE_PAD and state["status"] == "playing":
            state["status"] = "fading"
            if state["song"]:
                launchpad.set_led(state["song"]["pad"], LED_ORANGE)
            metronome.fade()
            refresh()

    launchpad.set_callback(on_pad)

    # ── 런치패드 연결 (하드웨어 없어도 GUI는 동작) ───────────
    try:
        in_name, out_name = launchpad.start()
        print(f"연결됨: {in_name}")
        for s in SONGS:
            launchpad.set_led(s["pad"], LED_BLUE)
        launchpad.set_led(FADE_PAD, LED_OFF)
    except Exception as e:
        print(f"[경고] 런치패드 연결 실패: {e}")
        print("  GUI 전용 모드로 실행 중 (MIDI 없음)")

    # ── 실행 ─────────────────────────────────────────────────
    try:
        root.mainloop()
    finally:
        metronome.stop()
        launchpad.stop()


if __name__ == "__main__":
    main()
