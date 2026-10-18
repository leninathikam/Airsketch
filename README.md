# AirSketch

AirSketch was built during HackGB (October 17–18, 2026) for the Education track.

## Problem

In a lecture, the board and the spoken explanation live in different places. A presenter writes on a whiteboard or slides, students hear the talk, and the useful review material is assembled afterward by hand. That split makes it easy to lose the connection between what was drawn and what was said.

## Solution

AirSketch is a lecture workspace on one laptop. The webcam tracks one hand so the presenter can write on the live video. The browser records the lecture. Google Speech-to-Text turns that audio into a transcript. Generate turns the transcript into study bullets and quiz questions, then Export saves a formatted notes page.

The presenter pinches a thumb and index finger together to draw a continuous line at the index tip. Separating those fingers lifts the pen and leaves the line. Raising the index and middle fingers erases. Raising three fingers changes color. A held fist clears the board. Camera and microphone are separate controls.

## Architecture

```text
Browser (React, localhost:3000)
  camera frames, microphone clips, notebook, export
        |
        | loopback HTTP, one session token per lecture tab
        v
Flask API (127.0.0.1:5000)
  webcam worker, MediaPipe hand landmarks, gesture rules, drawing
        |
        | transcript text only
        v
Google Speech-to-Text
Modal function airsketch-notes  ->  Gemini study notes
        |
        | if Modal or Gemini fails
        v
Local extractive summary (no quiz)
```

The webcam never leaves the laptop. Only audio goes to Speech-to-Text, and only the finished transcript goes to Gemini. Personal notes stay in the browser tab and are not sent to the model.

MediaPipe Hands supplies the 21 hand landmarks. Draw, erase, color, and clear are geometric rules on those landmarks. No custom gesture model is trained.

A fuller walkthrough of requests, the camera lease, and note generation is in `HOW_IT_WORKS.md`.

## AI disclosure

This disclosure covers AI assistants and third-party APIs used in AirSketch.

- **Cursor AI coding assistant** was used during HackGB to write and revise this application, including the React page, the Flask server, gesture rules, and this README. The running product does not call that assistant.
- **MediaPipe Hands** detects the hand on each camera frame. Gesture names are then chosen by local distance rules.
- **Google Cloud Speech-to-Text** (Chirp 3, location `us`) transcribes microphone clips of about 20 seconds. It is used only when Google credentials are set.
- **Google Gemini** (`gemini-3-flash-preview` by default) writes study bullets and quiz questions from the transcript. Each item is checked against the lecture text.
- **Modal** hosts the Generate step when `MODAL_SUMMARIZE_URL` is set. The deployed app is `airsketch-notes`. It calls Gemini with a key stored in a Modal secret. If that call fails, the laptop calls Gemini directly, then falls back to a local summary.

AI study notes can be wrong. Matching a quotation from the lecture does not prove every conclusion. Review them before relying on them.

## Setup

Use Python 3.12. MediaPipe does not install on Python 3.14. You also need Node.js and npm.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
python server/run.py
```

If `py -3.12` is not registered, create `.venv` with your Python 3.12 executable instead. On macOS or Linux, use `python3.12`, `source .venv/bin/activate`, and `cp .env.example .env`.

In `.env`, set `GOOGLE_APPLICATION_CREDENTIALS` and `GOOGLE_CLOUD_PROJECT` for transcription. Set `GEMINI_API_KEY` to an AI Studio key (it starts with `AIza`) for study notes. Do not commit `.env` or the service-account JSON file.

In a second terminal:

```powershell
cd client
npm install
$env:DANGEROUSLY_DISABLE_HOST_CHECK='true'
npm start
```

The host-check variable avoids a webpack dev-server startup error on this Windows setup. Open http://localhost:3000. The API listens only on http://127.0.0.1:5000.

### Modal

```powershell
pip install modal
modal setup
cd modal_notes
modal secret create airsketch-gemini --from-dotenv ..\.env --force
modal deploy app.py
```

Copy the printed `summarize` URL into `.env` as `MODAL_SUMMARIZE_URL`, restart `python server/run.py`, and click Generate once before a demo so the container is warm.

## Use

- **Camera** opens the webcam. **Stop camera** releases it. A slow device driver is reported instead of pretending the camera is already off.
- **Microphone** asks for permission on its own. Clips go to Speech-to-Text about every 20 seconds.
- Pinch the thumb and index finger to draw. Separate them to lift the pen. Raise two fingers to erase, three fingers to change color, and hold a fist to clear.
- **Generate** stops recording, sends the last clip, waits for uploads, and writes study notes. If clips failed, use **Retry uploads** first.
- The notebook has Transcript, Study notes, and My notes. Search the transcript and move between matches.
- **Export notes** saves the transcript, study notes, and personal notes as HTML, Markdown, or plain text. Personal notes are added with Ctrl/Cmd+Enter and exist only in this tab.
- **Focus mode** enlarges the whiteboard. Escape returns to the notebook.
- **Save board snapshot** downloads the current JPEG, including the camera image.
- **New lecture** drops the drawing, notes, and pending audio after confirmation.

Restarting the server or starting a new lecture discards in-memory notes and drawings. Export before you close the tab.

## Limits

Each upload is limited to 5 MB. A lecture allows 2,000 clips and 200,000 transcript characters. Recording pauses when several uploads are still unfinished. Drawings keep about the latest 20,000 points, and Undo clear keeps one previous board. At most 16 lecture sessions stay open, and an idle session expires after six hours. Two cloud operations may run at once, and one per lecture.

## Verification

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
cd client
npm test -- --watchAll=false --runInBand
npm run build
```

Tests mock the camera, microphone, and cloud services. They do not open the webcam or spend API credits.

## Project layout

- `server/run.py`: HTTP routes and lecture sessions.
- `server/camera.py`: camera ownership, reconnects, and the 10-second lease.
- `server/gestures.py`: landmark rules for draw, erase, color, and clear.
- `server/board.py`: strokes, erasing, clear hold, and undo.
- `server/notes_store.py`: ordered transcript.
- `server/cloud_notes.py`: Speech-to-Text, the Modal call, and local Gemini.
- `server/study_note_ai.py`: shared Gemini study-note logic.
- `server/summarize_notes.py`: local extractive fallback.
- `modal_notes/app.py`: Modal deployment for Generate.
- `client/src/App.js`: lecture page. 
- `client/src/lectureClient.js`: recording, uploads, and the session.
- `HOW_IT_WORKS.md`: request and frame-level detail.