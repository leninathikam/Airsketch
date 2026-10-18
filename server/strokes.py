from math import ceil, hypot


def stroke_points(previous, current, radius):
    """Fill frame-to-frame gaps with overlapping ink, preserving point erasing."""
    if previous is None:
        return [current]
    dx, dy = current[0] - previous[0], current[1] - previous[1]
    steps = max(1, ceil(hypot(dx, dy) / max(1, radius)))
    return [
        (round(previous[0] + dx * i / steps),
         round(previous[1] + dy * i / steps))
        for i in range(1, steps + 1)
    ]
