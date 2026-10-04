"""
Application settings and configuration for Car Plate Detection System.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(Path(BASE_DIR) / ".env")

# Model paths
MODEL_PATH = os.path.join(BASE_DIR, "models", "best.pt")
YOLO_BASE_MODEL_PATH = os.path.join(BASE_DIR, "models", "yolo11n.pt")

# Configuration files
CLASS_NAMES_PATH = os.path.join(BASE_DIR, "config", "class_names.txt")

# Database configuration
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "numberplate"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
}

# OCR configuration
OCR_CONFIDENCE_THRESHOLD = 0.5

# Video processing configuration
VIDEO_FRAME_INTERVAL = 5

# Data paths
DATA_DIR = os.path.join(BASE_DIR, "data")
VIDEOS_DIR = os.path.join(DATA_DIR, "videos")
TEST_VIDEO_PATH = os.path.join(VIDEOS_DIR, "tc.mp4")