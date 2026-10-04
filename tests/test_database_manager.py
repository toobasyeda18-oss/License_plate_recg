"""Tests for MySQL persistence operations."""

import unittest
from unittest.mock import patch

from utils import database_manager


class FakeCursor:
    def __init__(self):
        self.lastrowid = 37
        self.executed = []
        self.executemany_call = None
        self.closed = False

    def execute(self, query, parameters=None):
        self.executed.append((query, parameters))

    def executemany(self, query, parameters):
        self.executemany_call = (query, parameters)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class DatabaseManagerTests(unittest.TestCase):
    def test_analysis_and_all_detections_are_saved_in_one_transaction(self):
        connection = FakeConnection()
        detections = [
            {
                "plate": "ABC123",
                "confidence": 0.94,
                "timestamp": "00:00:03",
            },
            {
                "plate": "XYZ789",
                "confidence": 0.87,
                "timestamp": "00:00:09",
            },
        ]

        with patch.object(database_manager, "get_connection", return_value=connection):
            video_id = database_manager.save_analysis(
                "traffic.mp4", "stored.mp4", detections
            )

        self.assertEqual(video_id, 37)
        self.assertEqual(
            connection.cursor_instance.executed[0][1],
            ("traffic.mp4", "stored.mp4"),
        )
        self.assertEqual(
            connection.cursor_instance.executemany_call[1],
            [
                (37, "ABC123", 0.94, "00:00:03"),
                (37, "XYZ789", 0.87, "00:00:09"),
            ],
        )
        self.assertTrue(connection.committed)
        self.assertTrue(connection.cursor_instance.closed)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()
