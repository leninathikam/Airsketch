"""Rotation-tolerant geometric rules on MediaPipe's 21 landmarks."""
from math import hypot


def distance(a, b):
    return hypot(a.x - b.x, a.y - b.y)


def extended(points, tip):
    pip, mcp = points[tip - 2], points[tip - 3]
    return (distance(points[tip], points[0]) > distance(pip, points[0]) * 1.12
            and distance(points[tip], mcp) > distance(pip, mcp) * 1.45)


def classify_hand(hand, image_shape=None, drawing=False):
    p = hand.landmark
    # A pen grip curls the fingers too: test fingertip contact before fist/counts.
    index_length = sum(distance(p[a], p[b]) for a, b in ((5, 6), (6, 7), (7, 8)))
    # Stay in the pinch a little longer so a one-frame opening does not lift the pen.
    if index_length > .03 and distance(p[4], p[8]) < index_length * (.36 if drawing else .18):
        return "draw"
    fingers = tuple(extended(p, tip) for tip in (8, 12, 16, 20))
    palm = max(distance(p[0], p[9]), .01)
    # A fist must be compact; a relaxed or partially visible hand is not a clear.
    curled = all(distance(p[tip], p[tip - 3]) < palm * .65
                 and distance(p[tip], p[0]) < distance(p[tip - 2], p[0]) * .95
                 for tip in (8, 12, 16, 20))
    thumb_folded = distance(p[4], p[9]) < palm * .85
    if not any(fingers) and curled and thumb_folded:
        return "clear"
    if fingers == (True, True, True, False):
        return "color"
    if fingers == (True, True, False, False):
        return "erase"
    return "idle"
