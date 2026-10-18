"""Google Speech-to-Text and Gemini helpers. Keys stay in the environment."""

import base64
import json
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path


def load_local_env():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        current = os.environ.get(key)
        if not current:
            os.environ[key] = value
        elif key == "GOOGLE_APPLICATION_CREDENTIALS" and not os.path.isfile(current):
            os.environ[key] = value


def _post_json(url, payload, headers, timeout):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"Google API failed ({exc.code}): {detail}") from exc


_credentials = None
_credentials_path = None
_credentials_lock = threading.Lock()


def _speech_token():
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    global _credentials, _credentials_path
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not path or not os.path.isfile(path):
        raise RuntimeError("Speech-to-Text credentials file was not found.")
    with _credentials_lock:
        if _credentials is None or path != _credentials_path:
            _credentials = service_account.Credentials.from_service_account_file(
                path, scopes=["https://www.googleapis.com/auth/cloud-platform"])
            _credentials_path = path
        if not _credentials.valid:
            transport = Request()
            def bounded_request(*args, **kwargs):
                kwargs["timeout"] = 20
                return transport(*args, **kwargs)
            _credentials.refresh(bounded_request)
        return _credentials.token


def transcribe_audio(audio_bytes):
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set.")

    # Chirp 3 is regional. The global endpoint rejects this model.
    location = "us"
    url = (
        f"https://{location}-speech.googleapis.com/v2/projects/{project}"
        f"/locations/{location}/recognizers/_:recognize"
    )
    data = _post_json(
        url,
        {
            "config": {
                "autoDecodingConfig": {},
                "languageCodes": ["en-US"],
                "model": "chirp_3",
            },
            "content": base64.b64encode(audio_bytes).decode("ascii"),
        },
        {"Authorization": f"Bearer {_speech_token()}"},
        timeout=60,
    )
    parts = []
    for result in data.get("results", []):
        alternatives = result.get("alternatives") or []
        if alternatives:
            parts.append(alternatives[0].get("transcript", "").strip())
    return " ".join(part for part in parts if part)


def gemini_notes(transcript):
    from study_note_ai import generate_study_notes

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    model = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
    return generate_study_notes(transcript, api_key, model)


def modal_study_notes(transcript):
    import requests

    url = os.environ.get("MODAL_SUMMARIZE_URL", "").strip()
    if not url:
        raise RuntimeError("MODAL_SUMMARIZE_URL is not set.")
    payload = {"transcript": transcript}
    secret = os.environ.get("MODAL_WEBHOOK_SECRET", "").strip()
    if secret:
        payload["secret"] = secret
    response = requests.post(url, json=payload, timeout=180)
    if response.status_code >= 400:
        detail = response.text[:400]
        raise RuntimeError(f"Modal summarize failed ({response.status_code}): {detail}")
    data = response.json()
    if data.get("error"):
        raise RuntimeError(data["error"])
    text = data.get("text", "").strip()
    if not text:
        raise RuntimeError("Modal returned an empty study-note response.")
    return text
