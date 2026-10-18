"""Deploy: cd modal_notes && modal deploy app.py"""

import os
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[1]
STUDY_MODULE = ROOT / "server" / "study_note_ai.py"

app = modal.App("airsketch-notes")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("fastapi[standard]")
    .add_local_file(STUDY_MODULE, "/root/study_note_ai.py")
)

SECRET_NAME = "airsketch-gemini"


@app.function(
    image=image,
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    timeout=120,
)
def generate_study_notes_remote(transcript: str) -> str:
    import importlib.util

    spec = importlib.util.spec_from_file_location("study_note_ai", "/root/study_note_ai.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    model = os.environ.get("GEMINI_MODEL", "gemini-3-flash-preview")
    return module.generate_study_notes(transcript, os.environ["GEMINI_API_KEY"], model)


@app.function(image=image, secrets=[modal.Secret.from_name(SECRET_NAME)])
@modal.fastapi_endpoint(method="POST", docs=False)
def summarize(payload: dict):
    expected = os.environ.get("MODAL_WEBHOOK_SECRET", "").strip()
    if expected:
        token = (payload or {}).get("secret", "")
        if token != expected:
            return {"error": "Unauthorized"}, 401

    transcript = (payload or {}).get("transcript", "")
    if not isinstance(transcript, str) or not transcript.strip():
        return {"error": "transcript is required"}, 400
    try:
        text = generate_study_notes_remote.remote(transcript)
        return {"text": text, "source": "modal-gemini"}
    except Exception as exc:
        return {"error": str(exc)}, 502
