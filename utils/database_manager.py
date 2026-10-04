"""MySQL persistence for uploaded videos and their plate detections."""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()


from typing import Any

import mysql.connector
from mysql.connector import MySQLConnection
from mysql.connector.cursor import MySQLCursor

from config.settings import DB_CONFIG



def get_connection() -> MySQLConnection:
    """Open a connection to the configured MySQL database."""
    return mysql.connector.connect(**DB_CONFIG)


def initialize_database() -> None:
    """Create the application tables if they do not already exist."""
    connection = get_connection()
    cursor: MySQLCursor | None = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS videos (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                original_filename VARCHAR(255) NOT NULL,
                stored_filename VARCHAR(255) NOT NULL,
                uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS plate_detections (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                video_id BIGINT UNSIGNED NOT NULL,
                plate_number VARCHAR(32) NOT NULL,
                confidence DECIMAL(6, 5) NOT NULL,
                video_timestamp VARCHAR(16) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_plate_detections_video
                    FOREIGN KEY (video_id) REFERENCES videos(id)
                    ON DELETE CASCADE,
                UNIQUE KEY uq_video_plate (video_id, plate_number),
                INDEX ix_detections_plate (plate_number)
            ) ENGINE=InnoDB
            """
        )
        connection.commit()
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def save_analysis(
    original_filename: str,
    stored_filename: str,
    detections: list[dict[str, Any]],
) -> int:
    """Persist one analyzed video and its detections in a single transaction."""
    connection = get_connection()
    cursor: MySQLCursor | None = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO videos (original_filename, stored_filename)
            VALUES (%s, %s)
            """,
            (original_filename, stored_filename),
        )
        video_id = int(cursor.lastrowid)
        if detections:
            cursor.executemany(
                """
                INSERT INTO plate_detections
                    (video_id, plate_number, confidence, video_timestamp)
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (
                        video_id,
                        detection["plate"],
                        detection["confidence"],
                        detection["timestamp"],
                    )
                    for detection in detections
                ],
            )
        connection.commit()
        return video_id
    except mysql.connector.Error:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def get_video(video_id: int) -> dict[str, Any] | None:
    """Return one saved video record, or None when it does not exist."""
    connection = get_connection()
    cursor: MySQLCursor | None = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, original_filename, stored_filename, uploaded_at
            FROM videos
            WHERE id = %s
            """,
            (video_id,),
        )
        return cursor.fetchone()
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def get_video_detections(video_id: int) -> list[dict[str, Any]]:
    """Return saved plate detections ordered by their video timestamp."""
    connection = get_connection()
    cursor: MySQLCursor | None = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT plate_number AS plate, confidence, video_timestamp AS timestamp
            FROM plate_detections
            WHERE video_id = %s
            ORDER BY id
            """,
            (video_id,),
        )
        detections = cursor.fetchall()
        for detection in detections:
            detection["confidence"] = float(detection["confidence"])
        return detections
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def get_recent_videos(limit: int = 10) -> list[dict[str, Any]]:
    """Return recent analyses and the number of plates saved for each."""
    connection = get_connection()
    cursor: MySQLCursor | None = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT v.id, v.original_filename, v.uploaded_at,
                   COUNT(d.id) AS detection_count
            FROM videos AS v
            LEFT JOIN plate_detections AS d ON d.video_id = v.id
            GROUP BY v.id, v.original_filename, v.uploaded_at
            ORDER BY v.uploaded_at DESC, v.id DESC
            LIMIT %s
            """,
            (limit,),
        )
        return cursor.fetchall()
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()
