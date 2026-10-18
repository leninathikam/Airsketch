"""Single webcam owner with explicit lifecycle, reconnects, and a client lease."""
import logging
import os
import threading
import time

import cv2
import mediapipe as mp

from gestures import classify_hand


class Camera:
    def __init__(self):
        self.lock = threading.Lock()
        self.thread = None
        self.stop_event = threading.Event()
        self.owner = None
        self.state = "off"
        self.jpeg = None
        self.last_frame = 0
        self.lease = 0

    def start(self, owner, board):
        with self.lock:
            if self.thread and self.thread.is_alive():
                if self.owner != owner or self.stop_event.is_set():
                    raise ValueError("Camera is busy. Stop the other camera session first.")
                self.lease = time.monotonic()
                return
            self.owner = owner
            self.state = "starting"
            self.jpeg = None
            self.last_frame = 0
            self.lease = time.monotonic()
            self.stop_event = threading.Event()
            self.thread = threading.Thread(target=self._run, args=(board, self.stop_event), daemon=True)
            self.thread.start()

    def stop(self, owner):
        with self.lock:
            if self.owner != owner:
                return
            self.stop_event.set()
            worker = self.thread
            self.state = "stopping" if worker and worker.is_alive() else "off"
            self.jpeg = None
        if worker:
            worker.join(timeout=3)
        if worker and worker.is_alive():
            raise RuntimeError("Camera is still stopping; waiting for the device driver.")

    def snapshot(self, owner, renew=False):
        with self.lock:
            if owner != self.owner:
                return {"state": "off", "age": None}, None
            if renew and not self.stop_event.is_set():
                self.lease = time.monotonic()
            age = time.monotonic() - self.last_frame if self.last_frame else None
            state = self.state
            if state == "on" and (age is None or age > 3):
                state = "reconnecting"
            return {"state": state, "age": age}, self.jpeg if state == "on" else None

    def _open(self, stop):
        apis = (cv2.CAP_MSMF, cv2.CAP_DSHOW, cv2.CAP_ANY) if os.name == "nt" else (cv2.CAP_ANY,)
        for api in apis:
            if stop.is_set():
                break
            capture = cv2.VideoCapture(0, api)
            if capture.isOpened():
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                return capture
            capture.release()
        return None

    def _run(self, board, stop):
        capture = None
        failed = False
        attempts = 0
        try:
            with mp.solutions.hands.Hands(max_num_hands=1, min_detection_confidence=0.6,
                                          min_tracking_confidence=0.6) as hands:
                while not stop.is_set():
                    with self.lock:
                        expired = time.monotonic() - self.lease > 10
                    if expired:
                        stop.set()
                        break
                    if capture is None:
                        if attempts >= 3:
                            failed = True
                            break
                        attempts += 1
                        capture = self._open(stop)
                        if capture is None:
                            stop.wait(1)
                            continue
                    ok, frame = capture.read()
                    if not ok or frame is None:
                        board.tracking_lost()
                        capture.release()
                        capture = None
                        with self.lock:
                            self.state = "reconnecting"
                            self.jpeg = None
                        stop.wait(1)
                        continue
                    if stop.is_set():
                        break
                    frame = cv2.flip(frame, 1)
                    rgb = cv2.cvtColor(cv2.resize(frame, (320, 240)), cv2.COLOR_BGR2RGB)
                    rgb.flags.writeable = False
                    result = hands.process(rgb)
                    if result.multi_hand_landmarks:
                        hand = result.multi_hand_landmarks[0]
                        mp.solutions.drawing_utils.draw_landmarks(frame, hand, mp.solutions.hands.HAND_CONNECTIONS)
                        board.apply(classify_hand(hand), hand, frame.shape)
                    else:
                        board.tracking_lost()
                    ok, buffer = cv2.imencode(".jpg", board.paint(frame), [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if not ok:
                        raise RuntimeError("Unable to encode camera frame")
                    with self.lock:
                        self.jpeg = buffer.tobytes()
                        self.last_frame = time.monotonic()
                        self.state = "on"
        except Exception:
            failed = True
            logging.exception("Camera worker failed")
        finally:
            if capture is not None:
                capture.release()
            board.tracking_lost()
            with self.lock:
                self.state = "error" if failed and not stop.is_set() else "off"
                self.jpeg = None
