"""Turn one MediaPipe hand into a board action."""


def _distance(a, b):
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def _finger_extended(landmarks, tip, pip):
    wrist = landmarks[0]
    return _distance(landmarks[tip], wrist) > _distance(landmarks[pip], wrist) * 1.12


def _pinched(points):
    """Thumb tip against index tip, scaled by the index finger itself.

    Comparing to the palm was too loose: 42% of the palm is wider than a
    real pinch, so a pointing or relaxed hand still drew.
    """
    finger = _distance(points[5], points[8])
    if finger < 1e-4:
        return False
    tips = _distance(points[4], points[8])
    index_out = _finger_extended(points, 8, 6)
    return index_out and tips < finger * 0.55


def classify_hand(hand_landmarks):
    points = hand_landmarks.landmark
    index = _finger_extended(points, 8, 6)
    middle = _finger_extended(points, 12, 10)
    ring = _finger_extended(points, 16, 14)
    pinky = _finger_extended(points, 20, 18)
    raised = sum((index, middle, ring, pinky))

    if index and middle and ring and not pinky:
        return "color"
    if index and middle and not ring and not pinky:
        return "erase"
    if _pinched(points):
        return "draw"
    if raised == 0:
        return "clear"
    return "idle"
