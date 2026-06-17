SONGS = [
    {"id": 1, "pad": 81, "name": "Song 01", "bpm": 120, "time_sig": "4/4"},
    {"id": 2, "pad": 82, "name": "Song 02", "bpm": 128, "time_sig": "4/4"},
    {"id": 3, "pad": 83, "name": "Song 03", "bpm": 140, "time_sig": "4/4"},
    {"id": 4, "pad": 84, "name": "Song 04", "bpm":  95, "time_sig": "3/4"},
    {"id": 5, "pad": 85, "name": "Song 05", "bpm": 110, "time_sig": "4/4"},
    {"id": 6, "pad": 86, "name": "Song 06", "bpm": 175, "time_sig": "4/4"},
    {"id": 7, "pad": 87, "name": "Song 07", "bpm":  80, "time_sig": "6/8"},
    {"id": 8, "pad": 88, "name": "Song 08", "bpm": 150, "time_sig": "4/4"},
]

FADE_PAD      = 19   # 오른쪽 사이드 맨 아래 → Fade
STOP_PAD      = 29   # 오른쪽 사이드 아래서 두 번째 → Fade
MUTE_PAD      = 18   # 그리드 8행 8열 → Mute
INST_STOP_PAD = 28   # 뮤트(18) 바로 위 → Stop

FADE_DURATION = 1.0

LED_OFF    = 0
LED_GREEN  = 21
LED_ORANGE = 9
LED_BLUE   = 45
LED_RED    = 5

# 위에서 6번째 행 (31~38) → 볼륨 조절 (8단계)
VOLUME_PADS = [31, 32, 33, 34, 35, 36, 37, 38]

RESERVED_PADS = {18, 19, 28, 29, 39, 49, 59, 69, 79, 89} | set(VOLUME_PADS)

ALL_GRID_PADS = [
    r * 10 + c
    for r in range(8, 0, -1)
    for c in range(1, 9)
]
