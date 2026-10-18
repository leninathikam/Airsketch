"""Write an Excalidraw board that explains AirSketch."""

import json
import random
from pathlib import Path

random.seed(17)
elements = []


def uid():
    return "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(12))


def base(kind, x, y, w, h, **extra):
    item = {
        "id": uid(),
        "type": kind,
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": "#1e1e1e",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "seed": random.randint(1, 2_000_000_000),
        "version": 1,
        "versionNonce": random.randint(1, 2_000_000_000),
        "isDeleted": False,
        "boundElements": [],
        "updated": 1,
        "link": None,
        "locked": False,
    }
    item.update(extra)
    elements.append(item)
    return item


def card(x, y, w, h, fill, stroke="#3559c7"):
    return base(
        "rectangle",
        x,
        y,
        w,
        h,
        backgroundColor=fill,
        strokeColor=stroke,
        roundness={"type": 3},
    )


def label(x, y, text, size=20, color="#1d2a3a", width=None, align="left"):
    width = width or max(40, int(len(text) * size * 0.55))
    height = int(size * 1.35) * (text.count("\n") + 1)
    return base(
        "text",
        x,
        y,
        width,
        height,
        text=text,
        originalText=text,
        fontSize=size,
        fontFamily=2,
        textAlign=align,
        verticalAlign="top",
        strokeColor=color,
        autoResize=True,
        lineHeight=1.25,
        containerId=None,
    )


def arrow(x1, y1, x2, y2, color="#3559c7"):
    return base(
        "arrow",
        x1,
        y1,
        x2 - x1,
        y2 - y1,
        points=[[0, 0], [x2 - x1, y2 - y1]],
        strokeColor=color,
        endArrowhead="arrow",
        startArrowhead=None,
        roundness={"type": 2},
    )


def icon_circle(x, y, letter, fill):
    card(x, y, 44, 44, fill, fill)
    label(x + 12, y + 10, letter, 20, "#ffffff", 24, "left")


# Canvas
card(40, 30, 1520, 980, "#f4f7fb", "#d7dee8")
label(70, 52, "AirSketch", 40, "#24324a", 280)
label(70, 104, "A lecture whiteboard you draw with your hand", 20, "#5c6b7a", 640)

# Flow cards
boxes = [
    (70, 180, "1", "You", "Webcam sees the hand.\nMicrophone hears the lecture."),
    (430, 180, "2", "Laptop server", "MediaPipe finds the hand.\nRules decide draw, erase,\ncolor, or clear."),
    (790, 180, "3", "Lecture page", "Live board on the left.\nNotebook on the right."),
    (1150, 180, "4", "Cloud notes", "Google writes the transcript.\nModal + Gemini builds\nstudy notes and a quiz."),
]
fills = ["#e7f8f3", "#e8eefc", "#fff6e8", "#f3eaff"]
for (x, y, num, title, body), fill in zip(boxes, fills):
    card(x, y, 300, 210, fill)
    icon_circle(x + 18, y + 18, num, "#3559c7")
    label(x + 74, y + 26, title, 24, "#24324a", 200)
    label(x + 20, y + 84, body, 18, "#3d4b5f", 250)

for x in (370, 730, 1090):
    arrow(x, 285, x + 55, 285)

label(70, 420, "How a frame becomes ink", 22, "#24324a", 420)
steps = [
    (70, "Camera frame"),
    (330, "Find 21 hand points"),
    (620, "Name the gesture"),
    (890, "Update the drawing"),
    (1160, "Send one picture"),
]
for index, (x, text) in enumerate(steps):
    card(x, 460, 230, 64, "#ffffff")
    label(x + 16, 478, text, 18, "#24324a", 200)
    if index < len(steps) - 1:
        arrow(x + 230, 492, x + 258, 492, "#7d8aa2")

label(70, 560, "Gestures", 22, "#24324a", 180)
gestures = [
    (70, "#2aa88a", "Pinch", "Thumb and index together.\nThis is the pen. Hold it to write."),
    (430, "#3559c7", "Two fingers", "Index and middle up.\nErases ink near the fingertip."),
    (790, "#d9892b", "Three fingers", "Index, middle, and ring.\nChanges the pen color."),
    (1150, "#b1413c", "Fist", "Hold a closed fist.\nClears the board after a moment."),
]
for x, color, title, body in gestures:
    card(x, 600, 300, 150, "#ffffff", color)
    card(x, 600, 8, 150, color, color)
    label(x + 24, 616, title, 22, color, 240)
    label(x + 24, 654, body, 16, "#3d4b5f", 250)

label(70, 780, "What to show a judge", 22, "#24324a", 360)
demo = [
    (70, "Start camera, then pinch and write a word."),
    (560, "Turn on the microphone and speak one idea."),
    (1050, "Generate notes, then export the page."),
]
for index, (x, text) in enumerate(demo, start=1):
    card(x, 822, 450, 70, "#ffffff")
    icon_circle(x + 12, 835, str(index), "#24324a")
    label(x + 68, 844, text, 16, "#24324a", 360)

label(70, 920, "The camera never leaves the laptop. Only the transcript goes to Google and Modal.", 16, "#5c6b7a", 980)

out = Path(__file__).resolve().parents[1] / "AirSketch.excalidraw"
payload = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {
        "viewBackgroundColor": "#ffffff",
        "gridSize": None,
    },
    "files": {},
}
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(out)
