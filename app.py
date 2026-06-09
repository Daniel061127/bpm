#!/usr/bin/env python3
"""
Launchpad BPM Controller - 웹 서버
실행: python3 app.py  →  http://localhost:5001
"""
import json
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

from config import (
    SONGS as DEFAULT_SONGS,
    FADE_PAD, MUTE_PAD, FADE_DURATION,
    LED_OFF, LED_GREEN, LED_ORANGE, LED_BLUE, LED_RED,
    RESERVED_PADS, ALL_GRID_PADS,
)
from metronome import Metronome
from launchpad import Launchpad

app = Flask(__name__)
app.config['SECRET_KEY'] = 'lp-bpm-2024'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

metronome = Metronome()
metronome.set_fade_duration(FADE_DURATION)
launchpad = Launchpad()

# ── 곡 데이터 ─────────────────────────────────────────────
SONGS_FILE = Path(__file__).parent / 'songs.json'


def load_songs():
    if SONGS_FILE.exists():
        data = json.loads(SONGS_FILE.read_text(encoding='utf-8'))
    else:
        data = [dict(s) for s in DEFAULT_SONGS]
    for s in data:
        s.setdefault('time_sig', '4/4')
    return data


def save_songs():
    SONGS_FILE.write_text(
        json.dumps(songs, ensure_ascii=False, indent=2), encoding='utf-8'
    )


songs = load_songs()
pad_map: dict = {s['pad']: s for s in songs}


def rebuild_pad_map():
    pad_map.clear()
    pad_map.update({s['pad']: s for s in songs})


def next_pad():
    used = {s['pad'] for s in songs}
    for p in ALL_GRID_PADS:
        if p not in used and p not in RESERVED_PADS:
            return p
    return None


# ── 공유 상태 ─────────────────────────────────────────────
state = {
    'song': None,
    'bpm':  0.0,
    'status': 'stopped',   # stopped | playing | fading
    'muted': False,
    'launchpad': False,
}


# ── 이벤트 전송 ───────────────────────────────────────────
def emit_state():
    socketio.emit('state_change', {
        'status':    state['status'],
        'muted':     state['muted'],
        'song_id':   state['song']['id']   if state['song'] else None,
        'song_name': state['song']['name'] if state['song'] else None,
        'launchpad': state['launchpad'],
    })


def emit_beat():
    socketio.emit('beat', {'bpm': round(state['bpm'], 1)})


def emit_songs():
    socketio.emit('songs_update', songs)


# ── LED ───────────────────────────────────────────────────
def update_leds():
    if not launchpad.connected:
        return
    for s in songs:
        active = state['song'] and s['id'] == state['song']['id']
        if active:
            if state['muted']:
                color = LED_RED
            elif state['status'] == 'fading':
                color = LED_ORANGE
            else:
                color = LED_GREEN
        else:
            color = LED_BLUE
        launchpad.set_led(s['pad'], color)

    launchpad.set_led(FADE_PAD, LED_ORANGE if state['status'] != 'stopped' else LED_OFF)
    launchpad.set_led(MUTE_PAD, LED_RED    if state['muted']                else LED_OFF)


# ── 메트로놈 콜백 ─────────────────────────────────────────
def on_metro(metro_status, metro_bpm):
    prev = state['status']
    state['bpm']    = metro_bpm
    state['status'] = metro_status

    if metro_status == 'stopped':
        state['song']  = None
        state['muted'] = False
        update_leds()
        emit_state()
    else:
        emit_beat()
        if prev != metro_status:
            update_leds()
            emit_state()


metronome.set_state_callback(on_metro)


# ── 런치패드 콜백 ─────────────────────────────────────────
def on_pad(note):
    if note == FADE_PAD:
        do_fade()
    elif note == MUTE_PAD:
        do_mute()
    elif note in pad_map:
        do_play(pad_map[note])


launchpad.set_callback(on_pad)


# ── 동작 함수 ─────────────────────────────────────────────
def do_play(song):
    state.update(song=song, bpm=song['bpm'], status='playing', muted=False)
    update_leds()
    metronome.start(song['bpm'], song.get('time_sig', '4/4'))
    emit_state()


def do_fade():
    if state['status'] in ('playing', 'fading'):
        state['status'] = 'fading'
        metronome.fade()
        update_leds()
        emit_state()


def do_mute():
    if state['status'] == 'stopped':
        return
    state['muted'] = not state['muted']
    metronome.set_muted(state['muted'])
    update_leds()
    emit_state()


# ── HTTP 라우트 ───────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/state')
def api_state():
    return jsonify({
        'status':    state['status'],
        'bpm':       round(state['bpm'], 1),
        'muted':     state['muted'],
        'song_id':   state['song']['id']   if state['song'] else None,
        'song_name': state['song']['name'] if state['song'] else None,
        'launchpad': state['launchpad'],
    })


@app.route('/api/songs', methods=['GET'])
def api_get_songs():
    return jsonify(songs)


@app.route('/api/songs', methods=['POST'])
def api_add_song():
    pad = next_pad()
    if pad is None:
        return jsonify({'error': '사용 가능한 패드 없음'}), 400
    new_id   = max((s['id'] for s in songs), default=0) + 1
    new_song = {'id': new_id, 'pad': pad, 'name': f'Song {new_id:02d}', 'bpm': 120, 'time_sig': '4/4'}
    songs.append(new_song)
    rebuild_pad_map()
    if launchpad.connected:
        launchpad.set_led(pad, LED_BLUE)
    save_songs()
    emit_songs()
    return jsonify({'ok': True, 'song': new_song})


@app.route('/api/songs/<int:sid>', methods=['PUT'])
def api_update_song(sid):
    data = request.get_json() or {}
    for s in songs:
        if s['id'] == sid:
            if 'name' in data:
                s['name'] = str(data['name'])[:60]
            if 'bpm' in data:
                bpm = int(data['bpm'])
                if 20 <= bpm <= 400:
                    s['bpm'] = bpm
            if 'time_sig' in data and data['time_sig'] in ('4/4', '3/4', '2/4', '6/8'):
                s['time_sig'] = data['time_sig']
            break
    rebuild_pad_map()
    save_songs()
    return jsonify({'ok': True})


@app.route('/api/songs/<int:sid>', methods=['DELETE'])
def api_delete_song(sid):
    global songs
    target = next((s for s in songs if s['id'] == sid), None)
    if not target:
        return jsonify({'error': 'not found'}), 404
    if state['song'] and state['song']['id'] == sid:
        do_fade()
    if launchpad.connected:
        launchpad.set_led(target['pad'], LED_OFF)
    songs = [s for s in songs if s['id'] != sid]
    rebuild_pad_map()
    save_songs()
    emit_songs()
    return jsonify({'ok': True})


@app.route('/api/play/<int:sid>', methods=['POST'])
def api_play(sid):
    song = next((s for s in songs if s['id'] == sid), None)
    if not song:
        return jsonify({'error': 'not found'}), 404
    do_play(song)
    return jsonify({'ok': True})


@app.route('/api/stop', methods=['POST'])
def api_stop():
    do_fade()
    return jsonify({'ok': True})


@app.route('/api/mute', methods=['POST'])
def api_mute():
    do_mute()
    return jsonify({'ok': True})


# ── 진입점 ───────────────────────────────────────────────
if __name__ == '__main__':
    try:
        launchpad.start()
        for s in songs:
            launchpad.set_led(s['pad'], LED_BLUE)
        launchpad.set_led(FADE_PAD, LED_OFF)
        launchpad.set_led(MUTE_PAD, LED_OFF)
        state['launchpad'] = True
        print('런치패드 연결 완료')
    except Exception as e:
        print(f'[경고] 런치패드 없음: {e}')

    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print('  http://localhost:5001')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)
