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

FADE_PAD = 19   # 오른쪽 열 맨 아래 → fade 스탑
MUTE_PAD = 18   # 그리드 64번째 칸 (맨 아래 오른쪽) → 뮤트

FADE_DURATION = 5.0
MIN_FADE_BPM  = 20.0   # 미사용 (볼륨 페이드로 교체)

LED_OFF    = 0
LED_GREEN  = 21
LED_ORANGE = 9
LED_BLUE   = 45
LED_RED    = 5

# 오른쪽 열 + 뮤트 패드 = 곡 배정 제외
RESERVED_PADS = {18, 19, 29, 39, 49, 59, 69, 79, 89}

ALL_GRID_PADS = [
    r * 10 + c
    for r in range(8, 0, -1)
    for c in range(1, 9)
]
