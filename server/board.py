"""Stroke canvas drawn on top of each camera frame."""

from math import hypot, sqrt
import threading
import time
import copy

import cv2


class SketchBoard:
    def __init__(self):
        self._lock = threading.Lock()
        self.colors = [
            (255, 255, 255),
            (255, 140, 40),
            (70, 180, 70),
            (50, 50, 230),
            (40, 220, 240),
        ]
        self.color_index = 1
        self.width = 2
        self.strokes = []
        self.active = None
        self.smooth = None
        self.color_ready = True
        self.clear_since = None
        self.gesture = "idle"
        self.undo_strokes = None
        self.draw_frames = 0

    def clear(self):
        with self._lock:
            self._finish_stroke()
            self.undo_strokes = copy.deepcopy(self.strokes)
            self.strokes = []
            self.active = None
            self.smooth = None
            self.clear_since = None

    def apply(self, gesture, hand_landmarks, image_shape):
        height, width = image_shape[:2]
        if gesture == "draw":
            thumb = hand_landmarks.landmark[4]
            index = hand_landmarks.landmark[8]
            raw = (
                int((thumb.x + index.x) * 0.5 * width),
                int((thumb.y + index.y) * 0.5 * height),
            )
        else:
            tip = hand_landmarks.landmark[8]
            raw = (int(tip.x * width), int(tip.y * height))
        with self._lock:
            point = self._smooth(*raw)
            self.gesture = gesture
            if gesture == "color":
                if self.color_ready:
                    self.color_index = (self.color_index + 1) % len(self.colors)
                    self.color_ready = False
            else:
                self.color_ready = True

            if gesture == "draw":
                # Ignore one or two noisy frames so a passing pinch does not ink.
                self.draw_frames += 1
                if self.draw_frames >= 4:
                    self._append_point(gesture, point)
            elif gesture == "erase":
                self.draw_frames = 0
                self._finish_stroke()
                self.smooth = None
                self._erase_near(point)
            else:
                self.draw_frames = 0
                self._finish_stroke()
                self.smooth = None

            if gesture == "clear":
                now = time.monotonic()
                if self.clear_since is None:
                    self.clear_since = now
                if now - self.clear_since >= 0.6 and self.strokes:
                    self.undo_strokes = copy.deepcopy(self.strokes)
                    self.strokes = []
            else:
                self.clear_since = None

    def tracking_lost(self):
        with self._lock:
            self._finish_stroke()
            self.smooth = None
            self.clear_since = None
            self.color_ready = True
            self.gesture = "idle"

    def undo_clear(self):
        with self._lock:
            if self.undo_strokes is not None:
                self.strokes = self.undo_strokes
                self.undo_strokes = None
                self.active = None
                self.smooth = None
                self.clear_since = None

    def paint(self, frame):
        with self._lock:
            strokes = [
                {
                    "tool": stroke["tool"],
                    "color": stroke["color"],
                    "width": stroke["width"],
                    "points": list(stroke["points"]),
                }
                for stroke in self.strokes
                if stroke["tool"] == "draw"
            ]
            if self.active and self.active["tool"] == "draw" and len(self.active["points"]) > 1:
                strokes.append({**self.active, "points": list(self.active["points"])})
            label = self.gesture
            color = self.colors[self.color_index]

        for stroke in strokes:
            for start, end in zip(stroke["points"], stroke["points"][1:]):
                cv2.line(frame, start, end, stroke["color"], stroke["width"], cv2.LINE_AA)

        cv2.putText(frame, f"Gesture: {label}", (16, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 4, cv2.LINE_AA)
        cv2.putText(frame, f"Gesture: {label}", (16, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)
        return frame

    def _smooth(self, x, y):
        if self.smooth is None:
            self.smooth = (x, y)
        else:
            self.smooth = (
                int(self.smooth[0] * 0.62 + x * 0.38),
                int(self.smooth[1] * 0.62 + y * 0.38),
            )
        return self.smooth

    def _append_point(self, tool, point):
        if self.active is None or self.active["tool"] != tool:
            self._finish_stroke()
            self.active = {
                "tool": tool,
                "color": self.colors[self.color_index],
                "width": self.width,
                "points": [point],
            }
            return
        previous = self.active["points"][-1]
        if hypot(point[0] - previous[0], point[1] - previous[1]) >= 2:
            self.active["points"].append(point)
            if len(self.active["points"]) >= 1000:
                self._finish_stroke()
                self._append_point(tool, point)

    def _finish_stroke(self):
        if self.active and len(self.active["points"]) > 1 and self.active["tool"] == "draw":
            self.strokes.append(self.active)
            # Bound per-frame drawing work and memory (oldest ink retires first).
            while sum(len(s["points"]) for s in self.strokes) > 20_000:
                self.strokes.pop(0)
        self.active = None

    def _erase_near(self, point, radius=40):
        # Clip each segment against the circle, preserving disconnected runs.
        kept = []
        for stroke in self.strokes:
            run = []
            for a, b in zip(stroke["points"], stroke["points"][1:]):
                dx, dy = b[0] - a[0], b[1] - a[1]
                fx, fy = a[0] - point[0], a[1] - point[1]
                aa = dx * dx + dy * dy
                bb = 2 * (fx * dx + fy * dy)
                cc = fx * fx + fy * fy - radius * radius
                cuts = [0.0, 1.0]
                discriminant = bb * bb - 4 * aa * cc
                if aa and discriminant > 0:
                    for root in ((-bb - sqrt(discriminant)) / (2 * aa),
                                 (-bb + sqrt(discriminant)) / (2 * aa)):
                        if 0 < root < 1:
                            cuts.append(root)
                cuts.sort()
                for lo, hi in zip(cuts, cuts[1:]):
                    mid = (lo + hi) / 2
                    if hypot(fx + mid * dx, fy + mid * dy) < radius:
                        if len(run) > 1:
                            kept.append({**stroke, "points": run})
                        run = []
                    else:
                        start = (round(a[0] + lo * dx), round(a[1] + lo * dy))
                        end = (round(a[0] + hi * dx), round(a[1] + hi * dy))
                        if not run:
                            run = [start]
                        if end != run[-1]:
                            run.append(end)
            if len(run) > 1:
                kept.append({**stroke, "points": run})
        self.strokes = kept[-2000:]
