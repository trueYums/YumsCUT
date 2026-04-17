"""
FastAPI application — YouTube → TikTok converter.
"""
import asyncio
import json
import logging
import os
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

import db
import push
from scheduler import cleanup_expired_files, run_scheduler
from worker import process_job, read_stats, request_cancel

# 1 job à la fois — ffmpeg exploite les 2 cores du container pleinement
executor = ThreadPoolExecutor(max_workers=1)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    logger.info("Database ready at %s", os.getenv("DB_PATH", "/data/app.db"))

    await cleanup_expired_files()

    scheduler_task = asyncio.create_task(run_scheduler())
    logger.info("Background scheduler started")

    yield

    scheduler_task.cancel()
    executor.shutdown(wait=False)
    logger.info("Shutdown complete")


app = FastAPI(title="YouTube → TikTok Converter", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class StartJobRequest(BaseModel):
    url: str
    session_id: str


class PushSubscribeRequest(BaseModel):
    session_id: str
    subscription: dict


# ---------------------------------------------------------------------------
# Worker thread helpers
# ---------------------------------------------------------------------------

def _make_update_cb(job_id: str):
    """Return a sync callback that updates the job row from a worker thread."""
    def callback(
        status: str,
        message: str,
        current_part: int | None = None,
        total_parts: int | None = None,
        error: str | None = None,
        title: str | None = None,
    ):
        kwargs: dict = {"status": status, "progress_message": message}
        if current_part is not None:
            kwargs["current_part"] = current_part
        if total_parts is not None:
            kwargs["total_parts"] = total_parts
        if error is not None:
            kwargs["error"] = error
        if title is not None:
            kwargs["title"] = title
        db.update_job_sync(job_id, **kwargs)

    return callback


def _make_file_cb(job_id: str, session_id: str):
    """Return a sync callback that registers a completed segment file."""
    def callback(
        file_id: str,
        filename: str,
        filepath: str,
        part_num: int,
        total_parts: int,
        title: str,
    ):
        db.create_file_sync(
            file_id, job_id, session_id,
            filename, filepath,
            part_num, total_parts, title,
        )
        logger.info("Registered file: %s", filename)

    return callback


def _run_job(job_id: str, session_id: str, url: str) -> None:
    """Entry point executed in the thread pool."""
    update_cb = _make_update_cb(job_id)
    file_cb = _make_file_cb(job_id, session_id)

    try:
        process_job(job_id, session_id, url, update_cb, file_cb)
    except Exception:
        # Error already recorded by process_job via update_cb
        return

    # Send push notification when done
    _send_completion_push(job_id, session_id)


def _send_completion_push(job_id: str, session_id: str) -> None:
    sub = db.get_push_subscription_sync(session_id)
    if not sub:
        return

    job = db.get_job_sync(job_id)
    if not job:
        return

    title_str = (job.get("title") or "votre vidéo")[:40]
    total = job.get("total_parts") or 1
    plural = "s" if total > 1 else ""

    push.send_push_notification(
        sub["subscription_json"],
        "Traitement terminé ✓",
        f"« {title_str} » est prête — {total} partie{plural} disponible{plural}",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.get("/sw.js")
async def service_worker():
    return FileResponse(
        "static/sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/stats")
async def stats():
    return read_stats()


@app.post("/api/jobs")
async def start_job(request: StartJobRequest):
    url = request.url.strip()
    session_id = request.session_id.strip()

    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL invalide — doit commencer par http:// ou https://")

    if len(session_id) < 8:
        raise HTTPException(status_code=400, detail="session_id invalide")

    await db.ensure_session(session_id)

    job_id = str(uuid.uuid4())
    await db.create_job(job_id, session_id, url)

    loop = asyncio.get_running_loop()
    loop.run_in_executor(executor, _run_job, job_id, session_id, url)

    logger.info("Job %s started for session %s", job_id, session_id)
    return {"job_id": job_id, "status": "pending"}


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, session_id: str = Query(...)):
    job = await db.get_job(job_id)
    if not job or job["session_id"] != session_id:
        raise HTTPException(status_code=404, detail="Job non trouvé")
    if job["status"] not in ("pending", "downloading", "processing"):
        raise HTTPException(status_code=400, detail="Ce job n'est plus annulable")

    request_cancel(job_id)
    # Pre-mark as cancelled so the next poll reflects it immediately
    await db.update_job(job_id, status="cancelled", progress_message="Annulation en cours…")
    logger.info("Cancel requested for job %s", job_id)
    return {"status": "cancelling"}


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str, session_id: str = Query(...)):
    job = await db.get_job(job_id)
    if not job or job["session_id"] != session_id:
        raise HTTPException(status_code=404, detail="Job non trouvé")
    return job


@app.get("/api/files")
async def list_files(session_id: str = Query(...)):
    return await db.get_files_for_session(session_id)


@app.delete("/api/files/{file_id}")
async def delete_file(file_id: str, session_id: str = Query(...)):
    file = await db.delete_file(file_id, session_id)
    if not file:
        raise HTTPException(status_code=404, detail="Fichier non trouvé ou accès refusé")

    filepath = file["filepath"]
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError as exc:
            logger.error("Could not delete physical file %s: %s", filepath, exc)

    return {"status": "deleted"}


@app.get("/api/download/{file_id}")
async def download_file(file_id: str, session_id: str = Query(...)):
    file = await db.get_file(file_id)
    if not file or file["session_id"] != session_id:
        raise HTTPException(status_code=404, detail="Fichier non trouvé")
    if file["status"] != "available":
        raise HTTPException(status_code=410, detail="Fichier expiré ou supprimé")

    filepath = file["filepath"]
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Fichier physique introuvable")

    return FileResponse(
        filepath,
        media_type="video/mp4",
        filename=file["filename"],
        headers={
            "Content-Disposition": f'attachment; filename="{file["filename"]}"',
            "Accept-Ranges": "bytes",
        },
    )


@app.post("/api/push/subscribe")
async def subscribe_push(request: PushSubscribeRequest):
    subscription_json = json.dumps(request.subscription)
    await db.save_push_subscription(request.session_id, subscription_json)
    return {"status": "subscribed"}


@app.get("/api/push/vapid-key")
async def vapid_key():
    key = push.get_vapid_public_key()
    if not key:
        raise HTTPException(status_code=503, detail="VAPID non configuré")
    return {"public_key": key}
