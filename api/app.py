"""Flask application for uploading videos and reviewing plate detections."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from secrets import token_hex

import mysql.connector
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from utils import database_manager
from src.plate_detector import PlateDetector

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}
MAX_UPLOAD_SIZE = 500 * 1024 * 1024

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or token_hex(32),
    MAX_CONTENT_LENGTH=MAX_UPLOAD_SIZE,
    UPLOAD_FOLDER=PROJECT_ROOT / "instance" / "uploads",
)

_detector: PlateDetector | None = None


def get_detector() -> PlateDetector:
    """Load the model and OCR reader only when the first video is submitted."""
    global _detector
    if _detector is None:
        _detector = PlateDetector()
    return _detector


def allowed_video(filename: str) -> bool:
    """Return whether the uploaded file has a supported video extension."""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        try:
            try:
                recent_videos = database_manager.get_recent_videos()
            except mysql.connector.Error:
                app.logger.exception("Could not load recent analyses from MySQL")
                recent_videos = []
                flash("Results are saved, but recent analyses could not be loaded.", "error")
        except mysql.connector.Error:
            app.logger.exception("Could not load recent analyses from MySQL")
            recent_videos = []
            flash(
                "MySQL is not connected. Check the .env database settings and start MySQL.",
                "error",
            )
        return render_template(
            "index.html", detections=None, recent_videos=recent_videos
        )

    video = request.files.get("video")
    if video is None or not video.filename:
        flash("Choose a video file before starting analysis.", "error")
        return redirect(url_for("index"))

    original_name = secure_filename(video.filename)
    if not original_name or not allowed_video(original_name):
        flash("Choose a supported video file: MP4, MOV, MKV, AVI, M4V, or WEBM.", "error")
        return redirect(url_for("index"))

    upload_folder = Path(app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{Path(original_name).suffix.lower()}"
    video_path = upload_folder / stored_name
    video.save(video_path)

    try:
        detections = get_detector().process_video(video_path)
    except (OSError, RuntimeError, ValueError) as error:
        app.logger.exception("Video analysis failed")
        video_path.unlink(missing_ok=True)
        flash(f"Could not analyze this video: {error}", "error")
        return redirect(url_for("index"))

    try:
        video_id = database_manager.save_analysis(
            original_name, stored_name, detections
        )
    except mysql.connector.Error:
        app.logger.exception("Could not persist the analysis to MySQL")
        video_path.unlink(missing_ok=True)
        flash(
            "Could not save results to MySQL. Check the .env credentials, "
            "database name, and database permissions.",
            "error",
        )
        return redirect(url_for("index"))

    return redirect(url_for("analysis", video_id=video_id))


@app.route("/analyses/<int:video_id>")
def analysis(video_id: int):
    try:
        video = database_manager.get_video(video_id)
        if video is None:
            abort(404)
        detections = database_manager.get_video_detections(video_id)
    except mysql.connector.Error:
        app.logger.exception("Could not load analysis from MySQL")
        flash("Could not load results. Check the MySQL connection and try again.", "error")
        return redirect(url_for("index"))

    average_confidence = (
        sum(item["confidence"] for item in detections) / len(detections)
        if detections
        else 0.0
    )
    recent_videos = database_manager.get_recent_videos()
    return render_template(
        "index.html",
        detections=detections,
        average_confidence=average_confidence,
        video_name=video["original_filename"],
        video_url=url_for("uploaded_video", filename=video["stored_filename"]),
        video_id=video_id,
        recent_videos=recent_videos,
    )


@app.route("/uploads/<path:filename>")
def uploaded_video(filename: str):
    """Serve a previously uploaded video for in-page playback."""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.errorhandler(413)
def file_too_large(_error):
    flash("That video is larger than the 500 MB upload limit.", "error")
    return redirect(url_for("index"))


if __name__ == "__main__":
    database_manager.initialize_database()
    app.run(host="127.0.0.1", port=5000, debug=False)
