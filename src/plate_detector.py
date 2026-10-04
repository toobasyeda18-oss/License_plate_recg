"""Headless license plate detection and OCR for video files."""

import argparse
import re
from pathlib import Path
from typing import Any

import cv2
import easyocr
from ultralytics import YOLO

from config.settings import (
    MODEL_PATH,
    OCR_CONFIDENCE_THRESHOLD,
    TEST_VIDEO_PATH,
    VIDEO_FRAME_INTERVAL,
)


class PlateDetector:
    """Detect and recognize unique license plates in a video."""

    def __init__(self, model: Any = None, reader: Any = None) -> None:
        self.reader = reader if reader is not None else easyocr.Reader(["en"])
        self.model = model if model is not None else YOLO(MODEL_PATH)

    def perform_ocr(self, image_array: Any) -> tuple[str | None, float]:
        """Read text and average OCR confidence from a plate crop."""
        if image_array is None or image_array.size == 0:
            raise ValueError("The plate image is empty.")

        results = self.reader.readtext(image_array)
        if not results:
            return None, 0.0

        detected_text = " ".join(text for _, text, _ in results)
        confidence = sum(float(result[2]) for result in results) / len(results)
        return detected_text, confidence

    def process_video(self, video_path: str | Path) -> list[dict[str, Any]]:
        """Process all frames and return unique plates with confidence and time."""
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Could not open video source: {video_path}")

        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if fps <= 0:
            fps = 25.0

        detections: dict[str, dict[str, Any]] = {}
        processed_tracks: set[int] = set()
        last_track_attempt: dict[int, int] = {}
        frame_number = 0
        readable_frame = False

        try:
            while True:
                success, frame = capture.read()
                if not success:
                    break
                readable_frame = True
                if frame_number % VIDEO_FRAME_INTERVAL:
                    frame_number += 1
                    continue

                tracked_results = self.model.track(
                    frame, persist=True, imgsz=640, verbose=False
                )
                if not tracked_results or tracked_results[0].boxes is None:
                    frame_number += 1
                    continue

                boxes = tracked_results[0].boxes
                coordinates = boxes.xyxy.int().cpu().tolist()
                track_ids = (
                    boxes.id.int().cpu().tolist()
                    if boxes.id is not None
                    else [None] * len(coordinates)
                )
                frame_height, frame_width = frame.shape[:2]

                for coordinates_for_box, track_id in zip(coordinates, track_ids):
                    x1, y1, x2, y2 = coordinates_for_box
                    x1, x2 = max(0, x1), min(frame_width, x2)
                    y1, y2 = max(0, y1), min(frame_height, y2)
                    if x2 <= x1 or y2 <= y1:
                        continue

                    cv2.rectangle(frame, (x1, y1), (x2, y2), (73, 220, 178), 2)
                    if track_id is not None:
                        track_id = int(track_id)
                        if track_id in processed_tracks:
                            continue
                        if frame_number - last_track_attempt.get(track_id, -5) < 5:
                            continue
                        last_track_attempt[track_id] = frame_number
                    elif frame_number % 5:
                        continue

                    crop = cv2.resize(frame[y1:y2, x1:x2], (240, 80))
                    text, confidence = self.perform_ocr(crop)
                    plate = re.sub(r"[^A-Z0-9]", "", (text or "").upper())
                    if not plate or len(plate) < 3:
                        continue
                    if confidence < OCR_CONFIDENCE_THRESHOLD:
                        continue

                    total_seconds = int(frame_number / fps)
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    detection = detections.get(plate)
                    if detection is None:
                        detections[plate] = {
                            "plate": plate,
                            "confidence": round(confidence, 4),
                            "timestamp": timestamp,
                        }
                    elif confidence > detection["confidence"]:
                        detection["confidence"] = round(confidence, 4)

                    if track_id is not None:
                        processed_tracks.add(track_id)
                    cv2.putText(
                        frame,
                        f"{plate}  {confidence:.0%}",
                        (x1, max(y1 - 8, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (73, 220, 178),
                        2,
                    )

                frame_number += 1
        finally:
            capture.release()

        if not readable_frame:
            raise RuntimeError("The uploaded video contains no readable frames.")
        return list(detections.values())

    def detect_from_video(self, video_path: str | Path | None = None) -> list[dict[str, Any]]:
        """Compatibility entry point for processing the bundled sample video."""
        return self.process_video(video_path or TEST_VIDEO_PATH)


def main() -> None:
    """Run detection from the bundled video or a CLI-selected source."""
    parser = argparse.ArgumentParser(description="Run local license plate recognition.")
    parser.add_argument(
        "--source",
        default=str(TEST_VIDEO_PATH),
        help="Path to a video file (defaults to the bundled sample).",
    )
    args = parser.parse_args()

    print(f"Analyzing {args.source} ...")
    detections = PlateDetector().process_video(args.source)
    if not detections:
        print("No license plates were recognized.")
        return
    for detection in detections:
        print(
            f"{detection['timestamp']}  {detection['plate']}  "
            f"{detection['confidence']:.1%} confidence"
        )


if __name__ == "__main__":
    main()