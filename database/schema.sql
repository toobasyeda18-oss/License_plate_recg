CREATE DATABASE IF NOT EXISTS numberplate
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE numberplate;

CREATE TABLE IF NOT EXISTS videos (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    uploaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

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
) ENGINE=InnoDB;
