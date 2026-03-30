"""
Hook-Check AI — Tribe v2 Inference Server (Railway Edition)
Supports two inference modes:
  1. Python API mode  — imports tribe_v2 directly (preferred when installed via pip)
  2. Subprocess mode — calls a CLI script (fallback for custom installs)
"""

import os
import json
import uuid
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

INFERENCE_MODE = os.environ.get("INFERENCE_MODE", "api")
TRIBE_PATH   = Path(os.environ.get("TRIBE_PATH", "./tribe_v2"))
TRIBE_PYTHON = os.environ.get("TRIBE_PYTHON", "python")
TRIBE_SCRIPT = TRIBE_PATH / os.environ.get("TRIBE_SCRIPT", "infer.py")
HOOK_SECONDS = int(os.environ.get("HOOK_SECONDS", "8"))
PORT = int(os.environ.get("PORT", "8000"))
TEMP_DIR = Path(tempfile.gettempdir()) / "hook_check_ai"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Hook-Check AI — Tribe v2 Inference Server",
    description="Railway-hosted bridge between Tribe v2 and HookCheck.ai frontend.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def run_tribe_api(video_path: Path) -> dict:
    try:
        import tribe_v2 as tribe
        result = tribe.analyze(
            video_path=str(video_path),
            max_seconds=HOOK_SECONDS,
            output_format="dict",
        )
        return result
    except ImportError:
        raise RuntimeError("tribe_v2 is not installed. Run: pip install tribe-v2")
    except AttributeError:
        try:
            from tribe_v2 import VideoAnalyzer
            analyzer = VideoAnalyzer()
            return analyzer.analyze(str(video_path), max_seconds=HOOK_SECONDS)
        except Exception as e:
            raise RuntimeError(f"tribe_v2 API error: {e}")

def run_tribe_subprocess(video_path: Path) -> dict:
    cmd = [
        TRIBE_PYTHON, str(TRIBE_SCRIPT),
        "--video", str(video_path),
        "--output-format", "json",
        "--max-seconds", str(HOOK_SECONDS),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(TRIBE_PATH))
    if result.returncode != 0:
        raise RuntimeError(f"Tribe v2 inference failed (exit {result.returncode}):\n{result.stderr}")
    return _extract_json(result.stdout.strip())

def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    lines = text.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        try:
            return json.loads("\n".join(lines[i:]))
        except json.JSONDecodeError:
            continue
    raise ValueError(f"No valid JSON in Tribe v2 output:\n{text[:500]}")

def run_tribe_inference(video_path: Path) -> dict:
    if INFERENCE_MODE == "api":
        return run_tribe_api(video_path)
    return run_tribe_subprocess(video_path)

def clip_video(input_path: Path, output_path: Path, seconds: int = HOOK_SECONDS) -> Path:
    cmd = ["ffmpeg", "-y", "-i", str(input_path), "-t", str(seconds), "-c", "copy", str(output_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error: {result.stderr}")
    return output_path

def cleanup(*paths: Path):
    for p in paths:
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass

@app.get("/", tags=["health"])
async def root():
    return {"service": "Hook-Check AI — Tribe v2 (Railway)", "status": "running", "inference_mode": INFERENCE_MODE, "hook_seconds": HOOK_SECONDS, "port": PORT}

@app.get("/health", tags=["health"])
async def health():
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    if INFERENCE_MODE == "api":
        try:
            import tribe_v2  # noqa: F401
            tribe_ok = True
        except ImportError:
            tribe_ok = False
    else:
        tribe_ok = TRIBE_SCRIPT.exists()
    return {"status": "ok" if (tribe_ok and ffmpeg_ok) else "degraded", "tribe_available": tribe_ok, "inference_mode": INFERENCE_MODE, "ffmpeg_found": ffmpeg_ok}

@app.post("/process", tags=["inference"])
async def process_video(video: UploadFile = File(...), hook_seconds: Optional[int] = Form(None)):
    seconds = hook_seconds or HOOK_SECONDS
    uid = uuid.uuid4().hex[:8]
    ext = Path(video.filename or "upload.mp4").suffix or ".mp4"
    raw_path  = TEMP_DIR / f"raw_{uid}{ext}"
    clip_path = TEMP_DIR / f"clip_{uid}{ext}"
    try:
        with raw_path.open("wb") as f:
            f.write(await video.read())
        try:
            clip_video(raw_path, clip_path, seconds=seconds)
        except RuntimeError as e:
            raise HTTPException(status_code=422, detail=f"Video clipping failed: {e}")
        try:
            tribe_result = run_tribe_inference(clip_path)
        except (RuntimeError, ValueError) as e:
            raise HTTPException(status_code=500, detail=f"Tribe v2 error: {e}")
        return JSONResponse(content={"ok": True, "hook_seconds_analysed": seconds, "filename": video.filename, "tribe": tribe_result})
    finally:
        cleanup(raw_path, clip_path)

@app.post("/process/mock", tags=["development"])
async def process_video_mock(video: UploadFile = File(...), hook_seconds: Optional[int] = Form(None)):
    seconds = hook_seconds or HOOK_SECONDS
    return JSONResponse(content={"ok": True, "hook_seconds_analysed": seconds, "filename": video.filename, "tribe": {"description": "The video opens with a close-up of a person's face showing surprise, followed by rapid text animations on a dark background. High energy motion detected in the first 3 seconds.", "scenes": [{"start": 0.0, "end": 2.5, "label": "face_closeup", "confidence": 0.92}, {"start": 2.5, "end": 5.0, "label": "text_overlay", "confidence": 0.87}, {"start": 5.0, "end": 8.0, "label": "product_reveal", "confidence": 0.79}], "motion_score": 0.74, "visual_events": ["jump_cut_at_1.2s", "text_appears_at_2.5s", "zoom_in_at_4.0s"], "face_detected": True, "text_on_screen": ["Sabias que...?", "Sigue mirando"], "audio_energy": 0.68, "dominant_colors": ["#1a1a2e", "#e94560", "#ffffff"], "pace": "fast", "hook_type": "question_hook"}})

if __name__ == "__main__":
    uvicorn.run("inference_server:app", host="0.0.0.0", port=PORT, reload=False)
