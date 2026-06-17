#!/usr/bin/env python3
"""
Launchpad BPM Controller - 웹 서버
실행: python3 app.py  →  http://localhost:5001
"""
import json
import os
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, render_template, request, Response
from flask_socketio import SocketIO

from config import (
    SONGS as DEFAULT_SONGS,
    FADE_PAD, STOP_PAD, MUTE_PAD, INST_STOP_PAD, FADE_DURATION,
    LED_OFF, LED_GREEN, LED_ORANGE, LED_BLUE, LED_RED,
    RESERVED_PADS, ALL_GRID_PADS,
    VOLUME_PADS,
)
from metronome import Metronome
from launchpad import Launchpad

app = Flask(__name__)
app.config['SECRET_KEY'] = 'lp-bpm-2024'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

metronome = Metronome()
metronome.set_fade_duration(FADE_DURATION)
launchpad = Launchpad()

VOLUME_STEPS = len(VOLUME_PADS)

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


import sys as _sys

# PyInstaller 번들 실행 시 OS별 쓰기 가능한 경로 사용
if getattr(_sys, 'frozen', False):
    import platform as _platform
    if _platform.system() == 'Windows':
        _data_dir = Path(os.environ.get('APPDATA', '~')) / 'LaunchpadBPM'
    else:
        _data_dir = Path(os.path.expanduser('~/Library/Application Support/LaunchpadBPM'))
    _data_dir.mkdir(parents=True, exist_ok=True)
    SONGS_FILE = _data_dir / 'songs.json'

songs = load_songs()
pad_map: dict = {}


def _available_pads():
    return [p for p in ALL_GRID_PADS if p not in RESERVED_PADS]


def reassign_pads():
    """곡 목록 순서대로 패드를 재배정 (곡 1 → 첫 번째 패드)"""
    available = _available_pads()
    for i, s in enumerate(songs):
        s['pad'] = available[i] if i < len(available) else None
    rebuild_pad_map()
    save_songs()


def rebuild_pad_map():
    pad_map.clear()
    pad_map.update({s['pad']: s for s in songs if s.get('pad') is not None})


# 시작 시 패드 순서 동기화
reassign_pads()


# ── 공유 상태 ─────────────────────────────────────────────
state = {
    'song':         None,
    'pending_song': None,
    'bpm':          0.0,
    'status':       'stopped',
    'muted':        False,
    'launchpad':    False,
    'volume':       1.0,
}


# ── 이벤트 전송 ───────────────────────────────────────────
def emit_state():
    socketio.emit('state_change', {
        'status':          state['status'],
        'muted':           state['muted'],
        'song_id':         state['song']['id']         if state['song']         else None,
        'song_name':       state['song']['name']       if state['song']         else None,
        'pending_song_id': state['pending_song']['id'] if state['pending_song'] else None,
        'launchpad':       state['launchpad'],
        'volume':          state['volume'],
    })


def emit_beat(bi, n, ts, vol):
    socketio.emit('beat', {
        'bpm':        round(state['bpm'], 1),
        'beat_index': bi,
        'n_beats':    n,
        'time_sig':   ts,
        'vol':        round(vol, 3),
    })


def emit_songs():
    socketio.emit('songs_update', songs)


# ── LED ───────────────────────────────────────────────────
def update_leds():
    if not launchpad.connected:
        return
    for s in songs:
        if s.get('pad') is None:
            continue
        active = state['song'] and s['id'] == state['song']['id']
        if active:
            color = LED_RED    if state['muted']              else \
                    LED_ORANGE if state['status'] == 'fading' else \
                    LED_GREEN
        else:
            color = LED_BLUE
        launchpad.set_led(s['pad'], color)

    launchpad.set_led(FADE_PAD,      LED_ORANGE if state['status'] != 'stopped' else LED_OFF)
    launchpad.set_led(STOP_PAD,      LED_RED    if state['status'] == 'fading'  else LED_GREEN)
    launchpad.set_led(INST_STOP_PAD, LED_RED    if state['status'] != 'stopped' else LED_GREEN)
    launchpad.set_led(MUTE_PAD,      LED_RED    if state['muted']               else LED_BLUE)
    _update_volume_leds()


def _update_volume_leds():
    if not launchpad.connected:
        return
    level = round(state['volume'] * VOLUME_STEPS)
    for i, pad in enumerate(VOLUME_PADS):
        launchpad.set_led(pad, LED_GREEN if i < level else LED_OFF)


def init_leds():
    if not launchpad.connected:
        return
    for s in songs:
        if s.get('pad') is not None:
            launchpad.set_led(s['pad'], LED_BLUE)
    launchpad.set_led(FADE_PAD,      LED_OFF)
    launchpad.set_led(STOP_PAD,      LED_GREEN)
    launchpad.set_led(INST_STOP_PAD, LED_GREEN)
    launchpad.set_led(MUTE_PAD,      LED_BLUE)
    _update_volume_leds()


# ── 메트로놈 콜백 ─────────────────────────────────────────
def on_metro(metro_status, metro_bpm, beat_index, n_beats, time_sig, vol):
    prev            = state['status']
    state['bpm']    = metro_bpm
    state['status'] = metro_status

    if metro_status == 'stopped':
        state['song']         = None
        state['muted']        = False
        state['pending_song'] = None
        _stop_pad_blink()
        update_leds()
        emit_state()
    else:
        emit_beat(beat_index, n_beats, time_sig, vol)
        if prev != metro_status:
            update_leds()
            emit_state()


metronome.set_state_callback(on_metro)


# ── 런치패드 콜백 ─────────────────────────────────────────
def on_pad(note):
    if note in (FADE_PAD, STOP_PAD, INST_STOP_PAD):
        do_fade()
    elif note == MUTE_PAD:
        do_mute()
    elif note in VOLUME_PADS:
        idx = VOLUME_PADS.index(note)
        state['volume'] = (idx + 1) / VOLUME_STEPS
        _update_volume_leds()
        emit_state()
    elif note in pad_map:
        do_play(pad_map[note])


launchpad.set_callback(on_pad)


def on_launchpad_disconnect():
    state['launchpad'] = False
    emit_state()


launchpad.set_disconnect_callback(on_launchpad_disconnect)


# ── 런치패드 LED 깜빡임 ───────────────────────────────────
_blink_stop_evt = threading.Event()
_blink_stop_evt.set()


def _start_pad_blink(pad, color, interval=0.4):
    global _blink_stop_evt
    _blink_stop_evt.set()
    _blink_stop_evt = threading.Event()
    evt = _blink_stop_evt

    def _blink():
        toggle = True
        while not evt.wait(interval):
            if launchpad.connected:
                launchpad.set_led(pad, color if toggle else LED_OFF)
            toggle = not toggle

    threading.Thread(target=_blink, daemon=True).start()


def _stop_pad_blink():
    _blink_stop_evt.set()


# ── 런치패드 연결 감시 루프 (2초마다) ────────────────────
def _reconnect_loop():
    while True:
        try:
            time.sleep(2)
            hw = launchpad.is_available()

            if launchpad.connected and not hw:
                print('[런치패드] 연결 끊김 감지')
                launchpad.stop()
                state['launchpad'] = False
                _stop_pad_blink()
                emit_state()

            elif not launchpad.connected and hw:
                print('[런치패드] 재연결 시도...')
                try:
                    launchpad.stop()
                    time.sleep(0.3)
                    launchpad.start()
                    state['launchpad'] = True
                    init_leds()
                    update_leds()
                    emit_state()
                    print('[런치패드] 재연결 완료')
                except Exception as e:
                    print(f'[런치패드] 재연결 실패: {e}')
        except Exception as e:
            print(f'[reconnect_loop 오류] {e}')


threading.Thread(target=_reconnect_loop, daemon=True).start()


# ── 동작 함수 ─────────────────────────────────────────────
def do_play(song):
    if state['status'] != 'stopped':
        _stop_pad_blink()
        state['pending_song'] = song
        emit_state()

        def on_start():
            state['song']         = song
            state['bpm']          = song['bpm']
            state['muted']        = False
            state['pending_song'] = None
            _stop_pad_blink()
            update_leds()
            emit_state()

        metronome.start(song['bpm'], song.get('time_sig', '4/4'), on_start=on_start)
        if song.get('pad') and launchpad.connected:
            _start_pad_blink(song['pad'], LED_ORANGE)
    else:
        state.update(song=song, bpm=song['bpm'], status='playing', muted=False)
        update_leds()
        emit_state()
        metronome.start(song['bpm'], song.get('time_sig', '4/4'))


def do_fade():
    if state['status'] in ('playing', 'fading'):
        state['status']       = 'fading'
        state['pending_song'] = None
        _stop_pad_blink()
        metronome.clear_pending()
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
        'status':          state['status'],
        'bpm':             round(state['bpm'], 1),
        'muted':           state['muted'],
        'song_id':         state['song']['id']         if state['song']         else None,
        'song_name':       state['song']['name']       if state['song']         else None,
        'pending_song_id': state['pending_song']['id'] if state['pending_song'] else None,
        'launchpad':       state['launchpad'],
        'volume':          state['volume'],
    })


@app.route('/api/songs', methods=['GET'])
def api_get_songs():
    return jsonify(songs)


@app.route('/api/songs', methods=['POST'])
def api_add_song():
    new_id   = max((s['id'] for s in songs), default=0) + 1
    new_song = {'id': new_id, 'pad': None, 'name': f'Song {new_id:02d}', 'bpm': 120, 'time_sig': '4/4'}
    songs.append(new_song)
    reassign_pads()
    update_leds()
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
    songs = [s for s in songs if s['id'] != sid]
    reassign_pads()
    update_leds()
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


@app.route('/api/volume', methods=['POST'])
def api_volume():
    data = request.get_json() or {}
    vol = float(data.get('volume', 1.0))
    state['volume'] = max(1 / VOLUME_STEPS, min(1.0, round(vol * VOLUME_STEPS) / VOLUME_STEPS))
    _update_volume_leds()
    emit_state()
    return jsonify({'ok': True})


@app.route('/api/export')
def api_export():
    data = json.dumps(songs, ensure_ascii=False, indent=2)
    return Response(
        data,
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename="launchpad-bpm-scene.json"'}
    )


@app.route('/api/import', methods=['POST'])
def api_import():
    global songs
    try:
        data = request.get_json(force=True)
        if not isinstance(data, list):
            return jsonify({'error': '잘못된 형식입니다'}), 400
        for s in data:
            if not isinstance(s, dict) or 'name' not in s or 'bpm' not in s:
                return jsonify({'error': '곡 데이터 형식 오류'}), 400
            s.setdefault('time_sig', '4/4')
        # ID 재할당
        max_id = max((s.get('id', 0) for s in data), default=0)
        for s in data:
            if 'id' not in s:
                max_id += 1
                s['id'] = max_id
        songs = data
        reassign_pads()
        rebuild_pad_map()
        save_songs()
        if launchpad.connected:
            launchpad.clear()
            init_leds()
            update_leds()
        emit_songs()
        emit_state()
        return jsonify({'ok': True, 'count': len(songs)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/debug/midi')
def api_debug_midi():
    import mido
    try:
        inputs  = mido.get_input_names()
        outputs = mido.get_output_names()
    except Exception as e:
        inputs, outputs = [], [f'ERROR: {e}']
    return jsonify({
        'inputs':    inputs,
        'outputs':   outputs,
        'connected': launchpad.connected,
    })


@app.route('/api/reconnect', methods=['POST'])
def api_reconnect():
    try:
        launchpad.stop()
        time.sleep(0.3)
        launchpad.start()
        state['launchpad'] = True
        init_leds()
        update_leds()
        emit_state()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


# ── 진입점 ───────────────────────────────────────────────
if __name__ == '__main__':
    try:
        launchpad.start()
        state['launchpad'] = True
        init_leds()
        print('런치패드 연결 완료')
    except Exception as e:
        print(f'[경고] 런치패드 없음: {e}')

    port = int(os.environ.get('PORT', 5001))
    print(f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print(f'  http://localhost:{port}')
    print(f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
