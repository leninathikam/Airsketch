# How AirSketch works

## Architecture and authorization

React talks to a Flask API on loopback. On mount, the browser creates a lecture with `POST /session`
and the custom `X-AirSketch: 1` header. The API validates the Host and browser Origin and returns a
random capability token. Subsequent requests carry `X-Session-Token`. Tokens stay in browser memory,
never in frame URLs. Each lecture owns separate notes and a board. There is no camera activity at import.

A new lecture creates a new capability; deleting a lecture invalidates delayed transcription results.
The API bounds open sessions, input sizes, transcript size, and concurrent cloud calls. These controls
protect the intended local browser workflow; they are not a substitute for user authentication and
persistent storage if this application is later deployed as a shared service.

## Camera and drawing

`POST /camera/start` acquires the single webcam for one lecture. Its worker opens OpenCV capture and
MediaPipe Hands. Frame requests renew a 10-second lease. Stop signals the worker and waits for release;
closing a tab requests deletion, while lease expiry handles lost disconnect requests.

The worker mirrors each frame, resizes a copy to 320 by 240 for hand tracking, and applies a rule-based
gesture classification to the original frame. No custom model is trained. MediaPipe supplies the
learned hand detector; draw/erase/color/clear are geometric rules, not an agent or a trained classifier.

Pinching draws at the thumb/index midpoint. Movement is smoothed under the board lock. Tracking loss
finishes the active stroke and resets smoothing and the clear hold. A fist must remain detected for
0.6 elapsed seconds. Color changes are latched until the gesture changes. Erasing clips each polyline
segment against a circular eraser and splits surviving runs, including sparse segments whose endpoints
lie outside the eraser. Clear stores one undo snapshot. Old drawing points retire at the configured cap.

The worker paints and JPEG-encodes the board. React polls `/frame.jpg` about every 100 ms, displays the
whole image with `object-fit: contain`, and revokes old blob URLs. There is no MJPEG endpoint in this
version. A stale frame is replaced by reconnecting/error status. Capture failures retry with a bounded
number of camera-open attempts and are logged. Resources are released in `finally`.

## Audio and transcript ordering

The browser tests MediaRecorder formats before requesting microphone access. A recording generation
counter invalidates late permission results. Stop and component disposal release every audio track;
a late permission grant also releases its tracks immediately.

Recordings rotate every 20 seconds into self-contained clips. Each clip has a monotonically increasing
sequence within its lecture. A serial upload queue sends `audio` and `sequence` to `/transcribe`.
Failed uploads retain their audio and sequence for retry, and recording pauses on failures/backlog.
The backend hashes audio for idempotency: retrying the same sequence and bytes reuses the stored result;
different audio under the same sequence is rejected. Notes are joined in sequence order, not request
completion order. Credential objects and valid OAuth tokens are reused for cloud requests.

Generate first stops recording, waits for the final `dataavailable`/`stop` events to enqueue their audio,
then waits for the upload queue. Unresolved failed clips block generation. Transcript, summary,
operational status, and errors are separate state fields, so errors do not destroy lecture text.

## Study notes and export

`POST /summarize` snapshots the lecture transcript. With Gemini configured, it sends a separate system
instruction requiring lecture-grounded bullets and quiz answers, plus exact supporting quotations.
Structured JSON is validated for expected fields, item limits, successful completion, and evidence
matching the transcript. Unsupported or malformed output falls back to the local extractive summarizer.
The UI explicitly identifies the fallback and explains that no quiz was generated.

The local summarizer scores short transcript chunks by non-stop-word frequency and returns up to four
in their original order. It is an extractive heuristic, not a neural network. Evidence matching reduces
unsupported output but cannot fully verify the model's reasoning; no live accuracy claim is made.

Download creates an HTML file containing available notes and the transcript. Text is HTML-escaped
before limited Markdown formatting is applied. Personal comments remain in React state only.

## Regression coverage

Python tests cover geometric erasing, tracking loss, timed clear and undo, sequence ordering, duplicate
uploads, isolated sessions, authorization, input limits, delayed results, cloud fallback, grounded AI
parsing, and camera lifecycle. Frontend tests cover permission cancellation, final-clip synchronization,
serialized uploads and retries, recorder startup failure, disposal, stale frames, and late initialization.
Both suites use simulated hardware/services. The production bundle is built separately.
