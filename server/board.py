"""Thread-safe continuous ink with explicit gesture holds and undo clear."""
import copy
import threading
import time

import cv2
import numpy as np

from draw_vid import COLOR_HEX, COLOR_NAMES, PALETTE, DrawingState
from gestures import classify_hand


class SketchBoard:
    def __init__(self):
        self._lock = threading.Lock()
        self.circles = []
        self.undo_circles = None
        self.state = DrawingState()
        self.clear_since = None
        self.clear_latched = False
        self.cursor = None
        self.gesture = "idle"
        self.last_draw = float("-inf")
        self.erase_since = None
        self._layer = None
        self._mask = None
        self._stamped = 0
        self._dirty = True

    def clear(self):
        with self._lock:
            self._clear()

    def _clear(self):
        if self.circles:
            self.undo_circles = copy.deepcopy(self.circles)
        self.circles = []
        self.state.previous = None
        self.cursor = None
        self._dirty = True

    def apply(self, gesture, hand, image_shape, now=None):
        del gesture
        now = time.monotonic() if now is None else now
        with self._lock:
            action = classify_hand(hand, image_shape, self.gesture == "draw")
            if action == "draw":
                self.last_draw = now
            # Pen release passes through ambiguous shapes. Never destroy ink then.
            if action in ("erase", "clear") and now - self.last_draw < .5:
                action = "idle"
            if action == "erase":
                if self.erase_since is None:
                    self.erase_since = now
                if now - self.erase_since < .35:
                    action = "idle"
            else:
                self.erase_since = None
            self.gesture = action
            self.state.update_gesture(action.capitalize(), now)
            if action == "clear":
                if self.clear_since is None:
                    self.clear_since = now
                if now - self.clear_since >= .6 and not self.clear_latched:
                    self._clear()
                    self.clear_latched = True
            else:
                self.clear_since = None
                self.clear_latched = False
            h, w = image_shape[:2]
            # The pinch meets halfway between thumb and index; tracking the midpoint
            # cuts single-landmark jitter in half while writing.
            if action == "draw":
                raw_x = (hand.landmark[4].x + hand.landmark[8].x) * .5 * w
                raw_y = (hand.landmark[4].y + hand.landmark[8].y) * .5 * h
                point = (round(raw_x), round(raw_y))
            else:
                point = (round(hand.landmark[8].x * w), round(hand.landmark[8].y * h))
            self.cursor = self.state.previous if action == "draw" and self.state.previous else point
            if action == "draw":
                for position in self.state.points_for(point):
                    self.circles.append((position, PALETTE[self.state.color], self.state.radius))
                self.cursor = self.state.previous or point
                if len(self.circles) > 20000:
                    self.circles = self.circles[-20000:]
                    self._dirty = True
            elif action == "erase":
                kept = [
                    p for p in self.circles
                    if (p[0][0] - point[0]) ** 2 + (p[0][1] - point[1]) ** 2 > (35 + p[2]) ** 2
                ]
                if len(kept) != len(self.circles):
                    self.circles = kept
                    self._dirty = True

    def tracking_lost(self):
        with self._lock:
            self.state.update_gesture("No hand")
            self.erase_since = None
            self.gesture = "no hand"
            self.cursor = None
            self.clear_since = None

    def undo_clear(self):
        with self._lock:
            if self.undo_circles is not None:
                self.circles = self.undo_circles
                self.undo_circles = None
                self._dirty = True
            self.state.previous = None

    def set_width(self, width):
        if type(width) not in (int, float) or not 2 <= width <= 12:
            raise ValueError("Pen width must be between 2 and 12 pixels.")
        with self._lock:
            self.state.radius = max(1, round(width / 2))
            self.state.previous = None

    def status(self):
        with self._lock:
            return {
                "action": self.gesture,
                "color": COLOR_NAMES[self.state.color],
                "hex": COLOR_HEX[self.state.color],
                "width": self.state.radius * 2,
                "canUndo": self.undo_circles is not None,
            }

    def _blank_layer(self, shape):
        height, width = shape[:2]
        self._layer = np.zeros((height, width, 3), dtype=np.uint8)
        self._mask = np.zeros((height, width), dtype=np.uint8)
        self._stamped = 0

    def _stamp(self, ink, start):
        for point, ink_color, ink_radius in ink[start:]:
            center = (int(point[0]), int(point[1]))
            radius = int(ink_radius)
            cv2.circle(self._layer, center, radius, ink_color, -1, cv2.LINE_AA)
            cv2.circle(self._mask, center, radius, 255, -1, cv2.LINE_AA)
        self._stamped = len(ink)

    def paint(self, frame):
        with self._lock:
            ink = self.circles
            height, width = frame.shape[:2]
            if (self._layer is None or self._dirty
                    or self._layer.shape[0] != height or self._layer.shape[1] != width
                    or self._stamped > len(ink)):
                self._blank_layer(frame.shape)
                self._stamp(ink, 0)
                self._dirty = False
            elif self._stamped < len(ink):
                self._stamp(ink, self._stamped)
            mask = self._mask
            layer = self._layer
            cursor, action, radius = self.cursor, self.gesture, self.state.radius
            color = PALETTE[self.state.color]
        # Alpha-blend the anti-aliased stroke mask so curves do not turn into staircases.
        active = mask > 0
        if np.any(active):
            alpha = mask[active][:, None].astype(np.uint16)
            frame[active] = ((layer[active].astype(np.uint16) * alpha
                              + frame[active].astype(np.uint16) * (255 - alpha) + 127) // 255).astype(np.uint8)
        if cursor is not None:
            cursor_color = color if action in ("draw", "erase") else (80, 220, 120)
            ring = 35 if action == "erase" else radius + 4
            cv2.circle(frame, cursor, ring, (255, 255, 255), 3, cv2.LINE_AA)
            cv2.circle(frame, cursor, ring, cursor_color, 1, cv2.LINE_AA)
        return frame
