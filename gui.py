import tkinter as tk

# ── 색상 팔레트 ──────────────────────────────────────────────
BG     = "#1a1a2e"
PANEL  = "#0f0f1e"
FG     = "#e0e0e0"
GRAY   = "#4a5568"
GREEN  = "#00e87a"
ORANGE = "#ff8c00"
BLUE   = "#4d9fff"
ALT    = "#16213e"


class BpmGui:
    def __init__(self, root, songs):
        self.root = root
        self.songs = songs
        self._rows = {}

        self._bpm_var    = tk.StringVar(value="---")
        self._status_var = tk.StringVar(value="STOPPED")
        self._name_var   = tk.StringVar(value="---")
        self._status_lbl = None

        root.title("Launchpad BPM Controller")
        root.configure(bg=PANEL)
        root.geometry("580x500")
        root.resizable(True, True)
        self._build()

    # ── 레이아웃 구성 ────────────────────────────────────────
    def _build(self):
        # 상단 타이틀
        tk.Label(self.root, text="LAUNCHPAD  BPM  CONTROLLER",
                 bg=PANEL, fg=GRAY, font=("Helvetica", 9, "bold")).pack(pady=(12, 0))

        # 상태 패널
        stat = tk.Frame(self.root, bg=PANEL, pady=10)
        stat.pack(fill="x")

        # 왼쪽: 현재 곡
        left = tk.Frame(stat, bg=PANEL)
        left.pack(side="left", padx=24)
        tk.Label(left, text="NOW PLAYING", bg=PANEL, fg=GRAY,
                 font=("Helvetica", 8)).pack(anchor="w")
        tk.Label(left, textvariable=self._name_var, bg=PANEL, fg=FG,
                 font=("Helvetica", 14, "bold")).pack(anchor="w")

        # 가운데: BPM 숫자
        mid = tk.Frame(stat, bg=PANEL)
        mid.pack(side="left", expand=True)
        tk.Label(mid, textvariable=self._bpm_var, bg=PANEL, fg=GREEN,
                 font=("Courier", 54, "bold")).pack()
        tk.Label(mid, text="BPM", bg=PANEL, fg=GRAY,
                 font=("Helvetica", 9)).pack()

        # 오른쪽: 상태 텍스트
        right = tk.Frame(stat, bg=PANEL)
        right.pack(side="right", padx=24)
        self._status_lbl = tk.Label(right, textvariable=self._status_var,
                                     bg=PANEL, fg=GRAY,
                                     font=("Helvetica", 13, "bold"))
        self._status_lbl.pack()

        # 구분선
        tk.Frame(self.root, bg="#252540", height=1).pack(fill="x")

        # 테이블 영역
        tbl = tk.Frame(self.root, bg=BG)
        tbl.pack(fill="both", expand=True, padx=8, pady=8)

        # 컬럼 헤더
        hrow = tk.Frame(tbl, bg=PANEL, pady=6)
        hrow.pack(fill="x")
        for text, w, anchor in [
            ("#",        4,  "center"),
            ("Song Name", 24, "w"),
            ("BPM",       7,  "w"),
            ("Status",   14,  "w"),
        ]:
            tk.Label(hrow, text=text, bg=PANEL, fg=GRAY,
                     font=("Helvetica", 8, "bold"),
                     width=w, anchor=anchor).pack(side="left", padx=(10, 0))

        # 곡 행
        for i, song in enumerate(self.songs):
            bg = ALT if i % 2 == 0 else BG
            self._rows[song["id"]] = self._make_row(tbl, song, bg)

    def _make_row(self, parent, song, bg):
        frame = tk.Frame(parent, bg=bg, pady=8)
        frame.pack(fill="x")

        tk.Label(frame, text=str(song["id"]),
                 bg=bg, fg=GRAY, font=("Courier", 11),
                 width=4, anchor="center").pack(side="left", padx=(10, 0))

        tk.Label(frame, text=song["name"],
                 bg=bg, fg=FG, font=("Helvetica", 11),
                 width=24, anchor="w").pack(side="left")

        tk.Label(frame, text=str(song["bpm"]),
                 bg=bg, fg=BLUE, font=("Courier", 12, "bold"),
                 width=7, anchor="w").pack(side="left")

        sv = tk.StringVar(value="●")
        lbl = tk.Label(frame, textvariable=sv,
                        bg=bg, fg=GRAY, font=("Helvetica", 11),
                        width=14, anchor="w")
        lbl.pack(side="left")

        return {"sv": sv, "lbl": lbl}

    # ── 외부에서 호출하는 업데이트 (스레드 안전) ─────────────
    def update(self, status, song, bpm):
        self.root.after(0, self._apply, status, song, bpm)

    def _apply(self, status, song, bpm):
        if status == "stopped":
            self._bpm_var.set("---")
            self._status_var.set("STOPPED")
            self._status_lbl.config(fg=GRAY)
            self._name_var.set("---")
            for r in self._rows.values():
                r["sv"].set("●")
                r["lbl"].config(fg=GRAY)

        elif status == "playing":
            self._bpm_var.set(f"{int(bpm)}")
            self._status_var.set("PLAYING")
            self._status_lbl.config(fg=GREEN)
            self._name_var.set(song["name"] if song else "---")
            self._highlight(song, GREEN, "▶ Playing")

        elif status == "fading":
            self._bpm_var.set(f"{int(bpm)}" if bpm > 0 else "---")
            self._status_var.set("FADING...")
            self._status_lbl.config(fg=ORANGE)
            self._name_var.set(song["name"] if song else "---")
            self._highlight(song, ORANGE, "⟳ Fading")

    def _highlight(self, active_song, color, text):
        for sid, row in self._rows.items():
            if active_song and sid == active_song["id"]:
                row["sv"].set(text)
                row["lbl"].config(fg=color)
            else:
                row["sv"].set("●")
                row["lbl"].config(fg=GRAY)
