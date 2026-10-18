import time


from strokes import stroke_points

PALETTE = [(50, 50, 220), (205, 110, 35), (90, 125, 40), (45, 45, 45)]
COLOR_NAMES = ["Terracotta", "Blue", "Green", "Ink"]
COLOR_HEX = ["#dc3232", "#236ecd", "#287d5a", "#2d2d2d"]


class DrawingState:
    def __init__(self):
        self.previous = None
        self.action = "Idle"
        self.color = 3
        self.radius = 2
        self.color_since = None
        self.release_since = None
        self.color_latched = False

    def update_gesture(self, action, now=None):
        now = time.monotonic() if now is None else now
        if action == "Color":
            self.release_since = None
            if self.color_since is None:
                self.color_since = now
            if not self.color_latched and now - self.color_since >= .45:
                self.color = (self.color + 1) % len(PALETTE)
                self.color_latched = True
        else:
            self.color_since = None
            if action != "No hand":
                if self.release_since is None:
                    self.release_since = now
                if now - self.release_since >= .3:
                    self.color_latched = False
            else:
                self.release_since = None
        if action != "Draw":
            self.previous = None
        self.action = action

    def points_for(self, position):
        previous = self.previous
        if previous is not None:
            gap = ((position[0] - previous[0]) ** 2 + (position[1] - previous[1]) ** 2) ** .5
            if gap > 220:
                previous = None
            else:
                position = tuple(round(a * .35 + b * .65) for a, b in zip(previous, position))
        self.previous = position
        return stroke_points(previous, position, 1)
