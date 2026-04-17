"""
Video processing worker.
Runs in a ThreadPoolExecutor — all functions are synchronous.
"""
import json
import logging
import os
import re
import subprocess
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_WORKER_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.getenv("DATA_DIR", "/data")
FONT_PATH = os.getenv("FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
STATS_FILE = os.path.join(DATA_DIR, "stats.json")


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

_stats_lock = threading.Lock()


def _update_stats(videos_delta: int, segments_delta: int) -> None:
    """Increment persistent stats counters (thread-safe)."""
    with _stats_lock:
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {"videos_processed": 0, "segments_created": 0}
            data["videos_processed"] = data.get("videos_processed", 0) + videos_delta
            data["segments_created"] = data.get("segments_created", 0) + segments_delta
            data["last_updated"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z"
            tmp = STATS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, STATS_FILE)
        except Exception as exc:
            logger.warning("Could not update stats: %s", exc)


def read_stats() -> dict:
    """Return current stats dict (called from the API route)."""
    with _stats_lock:
        try:
            if os.path.exists(STATS_FILE):
                with open(STATS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
    return {"videos_processed": 0, "segments_created": 0, "last_updated": None}


# ---------------------------------------------------------------------------
# Cancellation support
# ---------------------------------------------------------------------------

_active_procs: dict = {}      # job_id → Popen currently running
_cancel_flags: set = set()    # job_ids marked for cancellation
_procs_lock = threading.Lock()


class JobCancelledError(Exception):
    pass


def request_cancel(job_id: str) -> None:
    """Signal a job to stop. Terminates the active subprocess immediately."""
    with _procs_lock:
        _cancel_flags.add(job_id)
        proc = _active_procs.get(job_id)
    if proc:
        try:
            proc.terminate()
        except OSError:
            pass


def _check_cancel(job_id: str) -> None:
    if job_id in _cancel_flags:
        raise JobCancelledError()


def _run_tracked(job_id: str, cmd: list, timeout: int) -> tuple[int, str, str]:
    """
    Run a subprocess and register it for cancellation.
    Returns (returncode, stdout, stderr).
    """
    _check_cancel(job_id)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with _procs_lock:
        _active_procs[job_id] = proc
    try:
        try:
            out_b, err_b = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.terminate()
            proc.wait()
            raise RuntimeError(f"Délai dépassé ({timeout}s)")
        if job_id in _cancel_flags:
            raise JobCancelledError()
        return (
            proc.returncode,
            out_b.decode("utf-8", errors="replace"),
            err_b.decode("utf-8", errors="replace"),
        )
    finally:
        with _procs_lock:
            _active_procs.pop(job_id, None)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _resolve_font_path() -> str | None:
    """Return absolute path to the font file, or None if not found."""
    fp = FONT_PATH
    if not fp:
        return None
    if not os.path.isabs(fp):
        fp = os.path.join(_WORKER_DIR, fp)
    return fp if os.path.exists(fp) else None

# Segment timing constants
TARGET_SECS = 179.0   # 2 min 59 s
MIN_SECS = 62.0       # 1 min 2 s


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def get_user_dir(session_id: str) -> Path:
    path = Path(DATA_DIR) / "users" / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# yt-dlp helpers
# ---------------------------------------------------------------------------

def get_video_info(url: str) -> dict:
    """Fetch metadata without downloading the video."""
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        "--no-warnings",
        url,
    ]
    logger.info("Fetching metadata: %s", url)
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp metadata error: {result.stderr.strip()}")
    return json.loads(result.stdout)


def download_video(job_id: str, url: str, output_path: str) -> str:
    """
    Download best quality ≤1080p as mp4 (cancellable).
    Returns the actual path of the downloaded file.
    """
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--no-warnings",
        "-f",
        (
            "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=1080]+bestaudio"
            "/best[height<=1080]"
            "/best"
        ),
        "--merge-output-format", "mp4",
        "-o", output_path,
        url,
    ]
    logger.info("Downloading video...")
    rc, _, stderr = _run_tracked(job_id, cmd, timeout=3600)
    if rc != 0:
        raise RuntimeError(f"yt-dlp download error: {stderr.strip()}")
    return output_path


# ---------------------------------------------------------------------------
# ffprobe helpers
# ---------------------------------------------------------------------------

def get_video_duration(filepath: str) -> float:
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        filepath,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe error: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def has_audio(filepath: str) -> bool:
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        filepath,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if result.returncode != 0:
        return False
    data = json.loads(result.stdout)
    return any(s.get("codec_type") == "audio" for s in data.get("streams", []))


# ---------------------------------------------------------------------------
# Segment calculation
# ---------------------------------------------------------------------------

def calculate_segments(total: float) -> list[tuple[float, float]]:
    """
    Returns list of (start, end) tuples in seconds.

    Rules:
    - Target segment length: 179 s
    - Minimum segment length: 62 s
    - remainder < 62 s → merge with last complete segment and split in 2 equal parts
    - remainder == 0   → perfect
    - remainder >= 62  → keep as final segment
    """
    n = int(total // TARGET_SECS)
    remainder = total - n * TARGET_SECS

    segments: list[tuple[float, float]] = []

    if n == 0:
        # Entire video is one segment (whatever the duration)
        segments.append((0.0, total))
        return segments

    remainder_is_zero = remainder < 0.1

    if remainder_is_zero:
        for i in range(n):
            segments.append((i * TARGET_SECS, (i + 1) * TARGET_SECS))
        return segments

    if remainder >= MIN_SECS:
        for i in range(n):
            segments.append((i * TARGET_SECS, (i + 1) * TARGET_SECS))
        segments.append((n * TARGET_SECS, total))
        return segments

    # remainder < MIN_SECS → merge last block + remainder, split in 2
    if n == 1:
        half = total / 2.0
        segments.append((0.0, half))
        segments.append((half, total))
        return segments

    # n >= 2
    last_start = (n - 1) * TARGET_SECS
    last_block = TARGET_SECS + remainder
    half = last_block / 2.0

    for i in range(n - 1):
        segments.append((i * TARGET_SECS, (i + 1) * TARGET_SECS))
    segments.append((last_start, last_start + half))
    segments.append((last_start + half, total))
    return segments


# ---------------------------------------------------------------------------
# FFmpeg encoding
# ---------------------------------------------------------------------------

def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Word-wrap text to max_chars per line. Returns list of lines."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= max_chars:
            current += " " + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _draw_text_box(
    draw: "ImageDraw.ImageDraw",
    text: str,
    font: "ImageFont.FreeTypeFont",
    y: int,
    canvas_w: int,
    pad: int,
) -> None:
    """Draw text centred horizontally with a white semi-transparent box behind it."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (canvas_w - tw) // 2
    draw.rectangle(
        [x - pad, y - pad, x + tw + pad, y + th + pad],
        fill=(255, 255, 255, 235),
    )
    draw.text((x, y), text, font=font, fill=(0, 0, 0, 255))


def _make_text_overlay(
    title_lines: list[str],
    part_text: str,
    font_path: str | None,
    width: int = 1080,
    height: int = 1920,
) -> str:
    """
    Render title lines + part number onto a transparent RGBA PNG (1080×1920).
    Returns the path of a temporary file — caller must delete it after use.
    Layout mirrors the old drawtext layout:
      - title lines : fontsize 54, centred in upper blurred zone (≈ y=328)
      - part text   : fontsize 58, y=1560
    """
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def load_font(size: int) -> "ImageFont.FreeTypeFont":
        if font_path:
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    font_title = load_font(54)
    font_part = load_font(58)

    line_height = 70
    total_h = len(title_lines) * line_height - (line_height - 54)
    start_y = max(20, 328 - total_h // 2)

    for i, line in enumerate(title_lines):
        _draw_text_box(draw, line, font_title, start_y + i * line_height, width, pad=16)

    _draw_text_box(draw, part_text, font_part, 1560, width, pad=18)

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name, "PNG")
    tmp.close()
    return tmp.name


def encode_segment(
    job_id: str,
    input_path: str,
    output_path: str,
    start: float,
    duration: float,
    title: str,
    part_number: int,
    total_parts: int,
    with_audio: bool,
) -> None:
    """
    Encode one segment into 1080×1920 portrait with blurred background.

    Layout:
    - Background: source scaled/cropped to 1080×1920 + heavy box blur
    - Centre:     source scaled to fit 1080 wide (maintains AR) → ~1080×607 for 16:9
    - Top text:   video title (≤40 chars), fontsize 48, centred in upper blurred zone
    - Bottom text: "Partie X / N", fontsize 52, centred in lower blurred zone
    """
    # Wrap title, then render title + part number as a transparent PNG overlay.
    # This avoids ffmpeg's drawtext filter entirely — no fontfile= path escaping
    # issues on Windows (ffmpeg libavfilter 11.x cannot handle drive-letter colons).
    title_lines = _wrap_text(title[:120], max_chars=28)
    part_text = f"Partie {part_number} / {total_parts}"
    font_path = _resolve_font_path()

    overlay_path: str | None = None
    try:
        overlay_path = _make_text_overlay(title_lines, part_text, font_path)

        # Simple filter graph: background blur + foreground scale/overlay + text overlay
        filter_complex = (
            "[0:v]split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "boxblur=luma_radius=40:luma_power=2[blurred];"
            "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[scaled];"
            "[blurred][scaled]overlay=x=(W-w)/2:y=(H-h)/2[composed];"
            "[composed][1:v]overlay=0:0[v]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", input_path,      # input 0: video
            "-loop", "1",
            "-i", overlay_path,    # input 1: text overlay PNG
            "-t", str(duration),   # output duration
            "-filter_complex", filter_complex,
            "-map", "[v]",
        ]

        if with_audio:
            cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "128k"]

        cmd += [
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-movflags", "+faststart",
            output_path,
        ]

        logger.info(
            "Encoding segment %d/%d  [%.2fs → %.2fs]",
            part_number, total_parts, start, start + duration,
        )
        rc, _, stderr = _run_tracked(job_id, cmd, timeout=1800)
        if rc != 0:
            logger.error("FFmpeg stderr (last 2000 chars):\n%s", stderr[-2000:])
            raise RuntimeError(
                f"FFmpeg failed on segment {part_number}/{total_parts}: "
                f"{stderr[-400:].strip()}"
            )
    finally:
        if overlay_path and os.path.exists(overlay_path):
            try:
                os.remove(overlay_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Main job processor
# ---------------------------------------------------------------------------

UpdateCallback = Callable[..., None]
FileCallback = Callable[[str, str, str, int, int, str], None]


def process_job(
    job_id: str,
    session_id: str,
    url: str,
    update_cb: UpdateCallback,
    file_cb: FileCallback,
) -> None:
    """
    Full pipeline: metadata → download → segment → encode.
    Called from ThreadPoolExecutor.

    update_cb(status, message, current_part=None, total_parts=None, error=None, title=None)
    file_cb(file_id, filename, filepath, part_num, total_parts, title)
    """
    user_dir = get_user_dir(session_id)
    job_dir = user_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    raw_path: str | None = None

    try:
        # ---- Step 1: Metadata ----
        update_cb("downloading", "Récupération des métadonnées...")
        _check_cancel(job_id)
        info = get_video_info(url)
        title = info.get("title") or "Vidéo sans titre"
        logger.info("Job %s | title: %s", job_id, title)
        update_cb("downloading", f"Téléchargement : {title[:50]}...", title=title)

        # ---- Step 2: Download ----
        raw_path = str(job_dir / "source.mp4")
        download_video(job_id, url, raw_path)

        # Verify the file exists (yt-dlp may use a different extension)
        if not os.path.exists(raw_path):
            candidates = sorted(job_dir.glob("source.*"))
            video_candidates = [
                p for p in candidates if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}
            ]
            if not video_candidates:
                raise RuntimeError("Fichier téléchargé introuvable après yt-dlp")
            raw_path = str(video_candidates[0])
            logger.warning("Source file found at non-mp4 path: %s", raw_path)

        logger.info("Job %s | source: %s", job_id, raw_path)
        _check_cancel(job_id)

        # ---- Step 3: Duration & segments ----
        duration = get_video_duration(raw_path)
        logger.info("Job %s | duration: %.2f s", job_id, duration)

        segments = calculate_segments(duration)
        total_parts = len(segments)
        logger.info("Job %s | %d segment(s)", job_id, total_parts)

        audio = has_audio(raw_path)
        logger.info("Job %s | audio: %s", job_id, audio)

        update_cb(
            "processing",
            f"Préparation de l'encodage ({total_parts} partie{'s' if total_parts > 1 else ''})...",
            current_part=0,
            total_parts=total_parts,
        )

        # ---- Step 4: Encode segments ----
        safe_title = re.sub(r"[^\w\s-]", "", title[:30]).strip().replace(" ", "_")
        if not safe_title:
            safe_title = "video"

        for idx, (seg_start, seg_end) in enumerate(segments):
            _check_cancel(job_id)
            part_num = idx + 1
            seg_dur = seg_end - seg_start

            update_cb(
                "processing",
                f"Encodage segment {part_num}/{total_parts}...",
                current_part=part_num - 1,
                total_parts=total_parts,
            )

            filename = f"{safe_title}_partie_{part_num:02d}_sur_{total_parts:02d}.mp4"
            out_path = str(job_dir / filename)

            encode_segment(
                job_id,
                raw_path, out_path,
                seg_start, seg_dur,
                title, part_num, total_parts,
                with_audio=audio,
            )

            file_id = str(uuid.uuid4())
            file_cb(file_id, filename, out_path, part_num, total_parts, title)

            update_cb(
                "processing",
                f"Segment {part_num}/{total_parts} terminé",
                current_part=part_num,
                total_parts=total_parts,
            )

        # ---- Step 5: Cleanup source ----
        try:
            os.remove(raw_path)
            logger.info("Job %s | source file deleted", job_id)
        except OSError as exc:
            logger.warning("Job %s | could not delete source: %s", job_id, exc)

        update_cb(
            "done",
            f"Terminé — {total_parts} partie{'s' if total_parts > 1 else ''} disponible{'s' if total_parts > 1 else ''}",
            current_part=total_parts,
            total_parts=total_parts,
        )
        _update_stats(videos_delta=1, segments_delta=total_parts)
        logger.info("Job %s | DONE", job_id)

    except JobCancelledError:
        logger.info("Job %s | CANCELLED by user", job_id)
        # Clean up partial files
        if raw_path and os.path.exists(raw_path):
            try:
                os.remove(raw_path)
            except OSError:
                pass
        with _procs_lock:
            _cancel_flags.discard(job_id)
        update_cb("cancelled", "Traitement annulé")

    except Exception as exc:
        logger.error("Job %s | FAILED: %s", job_id, exc, exc_info=True)
        update_cb("error", str(exc), error=str(exc))
        raise
