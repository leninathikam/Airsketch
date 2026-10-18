"""Loopback-only API. Each browser tab owns an isolated lecture capability."""
import hashlib
import os
import secrets
import threading
import time

from flask import Flask, Response, g, jsonify, request
from flask_cors import CORS

from board import SketchBoard
from camera import Camera
from cloud_notes import gemini_notes, load_local_env, modal_study_notes, transcribe_audio
from notes_store import NotesStore
from summarize_notes import summarize

load_local_env()
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
ORIGINS = {"http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5000", "http://127.0.0.1:5000"}
CORS(app, origins=list(ORIGINS), allow_headers=["Content-Type", "X-AirSketch", "X-Session-Token"])
sessions = {}
sessions_lock = threading.Lock()
cloud_slots = threading.BoundedSemaphore(2)
camera = Camera()


class Lecture:
    def __init__(self):
        self.notes = NotesStore()
        self.board = SketchBoard()
        self.cloud_lock = threading.Lock()
        self.last_seen = time.monotonic()
        self.closed = False


@app.before_request
def authorize():
    if request.host not in {"localhost:5000", "127.0.0.1:5000"}:
        return jsonify(error="Invalid API host."), 403
    origin = request.headers.get("Origin")
    if origin is not None and origin not in ORIGINS:
        return jsonify(error="Origin is not allowed."), 403
    if request.method == "OPTIONS":
        return None
    if request.path == "/session" and request.method == "POST":
        if request.headers.get("X-AirSketch") != "1":
            return jsonify(error="Missing application header."), 403
        return None
    token = request.headers.get("X-Session-Token", "")
    with sessions_lock:
        lecture = sessions.get(token)
        if lecture is None or lecture.closed or time.monotonic() - lecture.last_seen > 21600:
            return jsonify(error="Lecture expired. Start a new lecture."), 401
        lecture.last_seen = time.monotonic()
    g.lecture, g.token = lecture, token


@app.errorhandler(413)
def too_large(_error):
    return jsonify(error="Audio upload exceeds the 5 MB limit."), 413


@app.errorhandler(ValueError)
def invalid(error):
    return jsonify(error=str(error)), 400


@app.post("/session")
def create_session():
    with sessions_lock:
        for token, lecture in list(sessions.items()):
            if time.monotonic() - lecture.last_seen > 21600:
                lecture.closed = True
                del sessions[token]
        if len(sessions) >= 16:
            return jsonify(error="Too many open lectures. Close an unused lecture."), 429
        token = secrets.token_urlsafe(32)
        sessions[token] = Lecture()
    return jsonify(token=token), 201


@app.delete("/session")
def close_session():
    with sessions_lock:
        g.lecture.closed = True
    try:
        camera.stop(g.token)
    except RuntimeError:
        app.logger.warning("Camera stop pending on session close")
    with sessions_lock:
        sessions.pop(g.token, None)
    return jsonify(status="closed")


@app.post("/camera/start")
def start_camera():
    try:
        with sessions_lock:
            if g.lecture.closed:
                return jsonify(error="Lecture was closed."), 409
            camera.start(g.token, g.lecture.board)
    except ValueError as exc:
        return jsonify(error=str(exc)), 409
    return jsonify(state="starting")


@app.post("/camera/stop")
def stop_camera():
    try:
        camera.stop(g.token)
    except RuntimeError as exc:
        return jsonify(error=str(exc), state="stopping"), 503
    return jsonify(state="off")


@app.get("/camera/status")
def camera_status():
    return jsonify(camera.snapshot(g.token)[0])


@app.get("/frame.jpg")
def frame_jpg():
    status, jpg = camera.snapshot(g.token, renew=True)
    if jpg is None:
        return jsonify(**status), 503
    response = Response(jpg, mimetype="image/jpeg")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/clear_board")
def clear_board():
    g.lecture.board.clear()
    return jsonify(status="cleared")


@app.post("/undo_clear")
def undo_clear():
    g.lecture.board.undo_clear()
    return jsonify(status="restored")


@app.post("/notes")
def add_note():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object.")
    text, sequence = payload.get("text"), payload.get("sequence")
    if not isinstance(text, str) or len(text) > 10000:
        raise ValueError("Text must be a string of at most 10,000 characters.")
    g.lecture.notes.add(text, sequence, hashlib.sha256(text.encode()).hexdigest())
    return jsonify(status="saved", transcript=g.lecture.notes.text())


def begin_cloud():
    if not g.lecture.cloud_lock.acquire(blocking=False):
        return False
    if not cloud_slots.acquire(blocking=False):
        g.lecture.cloud_lock.release()
        return False
    return True


def end_cloud():
    cloud_slots.release()
    g.lecture.cloud_lock.release()


@app.post("/transcribe")
def transcribe():
    upload = request.files.get("audio")
    try:
        sequence = int(request.form.get("sequence", ""))
    except ValueError:
        raise ValueError("A numeric clip sequence is required.")
    if not 0 <= sequence < NotesStore.MAX_CLIPS:
        raise ValueError("Clip sequence is out of range.")
    if upload is None or upload.mimetype not in {"audio/webm", "audio/ogg", "audio/mp4"}:
        raise ValueError("Send a WebM, Ogg, or MP4 audio recording.")
    audio = upload.read()
    if not audio:
        raise ValueError("The audio clip was empty.")
    digest = hashlib.sha256(audio).hexdigest()
    if not begin_cloud():
        return jsonify(error="Transcription is busy. Retry this clip."), 429
    try:
        existing = g.lecture.notes.get(sequence)
        if existing is not None:
            if existing[1] != digest:
                return jsonify(error="Clip sequence conflicts with an existing clip."), 409
            text = existing[0]
        else:
            try:
                text = transcribe_audio(audio)
            except Exception:
                app.logger.exception("Transcription failed")
                return jsonify(error="Transcription failed. Check server credentials or retry the clip."), 502
            if g.lecture.closed:
                return jsonify(error="Lecture was closed."), 409
            g.lecture.notes.add(text, sequence, digest)
        return jsonify(text=text, transcript=g.lecture.notes.text(), sequence=sequence)
    finally:
        end_cloud()


@app.post("/summarize")
def summarize_notes():
    if not begin_cloud():
        return jsonify(error="Wait for pending audio before generating notes."), 429
    try:
        transcript = g.lecture.notes.text()
        if not transcript:
            raise ValueError("Record a lecture before generating notes.")
        modal_url = os.environ.get("MODAL_SUMMARIZE_URL", "").strip()
        if modal_url:
            try:
                return jsonify(text=modal_study_notes(transcript), source="modal-gemini")
            except Exception:
                app.logger.exception("Modal study-note generation failed")
        if os.environ.get("GEMINI_API_KEY"):
            try:
                return jsonify(text=gemini_notes(transcript), source="gemini")
            except Exception:
                app.logger.exception("Study-note generation failed")
                return jsonify(text=summarize(transcript), source="local",
                               warning="AI generation failed. Showing an extractive summary without a quiz.")
        return jsonify(text=summarize(transcript), source="local",
                       warning="AI is not configured. Showing an extractive summary without a quiz.")
    finally:
        end_cloud()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, threaded=True)
