"""Tests for the local upload and result pages."""

from io import BytesIO
import re
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from api import app as web_app
from utils import database_manager


class FakeDetector:
    def process_video(self, _video_path):
        return [
            {
                "plate": "ABC123",
                "confidence": 0.94,
                "timestamp": "00:00:03",
            }
        ]


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.uploads = TemporaryDirectory()
        web_app.app.config.update(
            TESTING=True,
            UPLOAD_FOLDER=self.uploads.name,
        )
        self.client = web_app.app.test_client()
        self.recent_videos_patch = patch.object(
            database_manager, "get_recent_videos", return_value=[]
        )
        self.recent_videos_patch.start()
        self.addCleanup(self.recent_videos_patch.stop)

    def tearDown(self):
        self.uploads.cleanup()

    def test_home_page_has_video_upload_interface(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="video"', response.data)
        self.assertIn(b"Analyze video", response.data)

    def test_unsupported_upload_is_rejected(self):
        response = self.client.post(
            "/",
            data={"video": (BytesIO(b"not a video"), "notes.txt")},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Choose a supported video file", response.data)

    def test_video_upload_displays_detections_and_video(self):
        persisted_video = {}

        def save_analysis(original_filename, stored_filename, _detections):
            persisted_video.update(
                original_filename=original_filename,
                stored_filename=stored_filename,
            )
            return 1

        with (
            patch.object(web_app, "get_detector", return_value=FakeDetector()),
            patch.object(
                database_manager, "save_analysis", side_effect=save_analysis
            ) as save,
            patch.object(
                database_manager,
                "get_video",
                side_effect=lambda _video_id: {"id": 1, **persisted_video},
            ),
            patch.object(
                database_manager,
                "get_video_detections",
                return_value=[
                    {
                        "plate": "ABC123",
                        "confidence": 0.94,
                        "timestamp": "00:00:03",
                    }
                ],
            ),
        ):
            response = self.client.post(
                "/",
                data={"video": (BytesIO(b"video bytes"), "traffic.mp4")},
                content_type="multipart/form-data",
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        save.assert_called_once()
        self.assertIn(b"ABC123", response.data)
        self.assertIn(b"94.0%", response.data)
        self.assertIn(b"Export CSV", response.data)
        self.assertIn(b"Source footage", response.data)
        video_url = re.search(rb'<video[^>]+src="([^"]+)"', response.data)
        self.assertIsNotNone(video_url)
        video_response = self.client.get(video_url.group(1).decode())
        self.assertEqual(video_response.data, b"video bytes")
        video_response.close()

    def test_empty_detection_set_shows_helpful_state(self):
        class EmptyDetector:
            def process_video(self, _video_path):
                return []

        def save_analysis(original_filename, stored_filename, _detections):
            return 2

        with (
            patch.object(web_app, "get_detector", return_value=EmptyDetector()),
            patch.object(
                database_manager, "save_analysis", side_effect=save_analysis
            ),
            patch.object(
                database_manager,
                "get_video",
                return_value={
                    "id": 2,
                    "original_filename": "traffic.mp4",
                    "stored_filename": "empty-video.mp4",
                },
            ),
            patch.object(database_manager, "get_video_detections", return_value=[]),
        ):
            response = self.client.post(
                "/",
                data={"video": (BytesIO(b"video bytes"), "traffic.mp4")},
                content_type="multipart/form-data",
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No plates recognized", response.data)
        self.assertIn(b"<strong>0.0<small>%</small></strong>", response.data)

    def test_processing_failure_is_shown_to_user(self):
        class BrokenDetector:
            def process_video(self, _video_path):
                raise RuntimeError("The video contains no readable frames.")

        with patch.object(web_app, "get_detector", return_value=BrokenDetector()):
            response = self.client.post(
                "/",
                data={"video": (BytesIO(b"bad video"), "traffic.mp4")},
                content_type="multipart/form-data",
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"The video contains no readable frames", response.data)

    def test_mysql_save_error_is_reported(self):
        import mysql.connector

        with (
            patch.object(web_app, "get_detector", return_value=FakeDetector()),
            patch.object(
                database_manager,
                "save_analysis",
                side_effect=mysql.connector.Error("database unavailable"),
            ),
        ):
            response = self.client.post(
                "/",
                data={"video": (BytesIO(b"video bytes"), "traffic.mp4")},
                content_type="multipart/form-data",
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Could not save results to MySQL", response.data)


if __name__ == "__main__":
    unittest.main()
