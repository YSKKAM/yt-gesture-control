"""
app/config/settings.py

Loads config/config.yaml and exposes a frozen Settings dataclass.
Falls back to safe defaults if file is missing or malformed.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Locate the config file relative to the project root
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "config.yaml"


# ---------------------------------------------------------------------------
# Dataclasses — one per section
# ---------------------------------------------------------------------------
@dataclass
class GestureConfig:
    min_displacement_x: float = 0.20
    max_displacement_y: float = 0.12
    direction_ratio: float = 2.5
    min_speed: float = 0.15
    max_gesture_duration_ms: int = 1500
    min_gesture_duration_ms: int = 120
    cooldown_ms: int = 1000
    min_stable_frames: int = 3


@dataclass
class CameraConfig:
    device_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 20


@dataclass
class HandTrackingConfig:
    min_detection_confidence: float = 0.75
    min_tracking_confidence: float = 0.70
    tracking_landmark: int = 9


@dataclass
class YouTubeControlConfig:
    websocket_port: int = 9876
    heartbeat_interval_s: int = 5


@dataclass
class LoggingConfig:
    log_file: str = "logs/ytgc.log"
    max_bytes: int = 5_242_880
    backup_count: int = 3
    level: str = "INFO"


@dataclass
class Settings:
    gesture: GestureConfig = field(default_factory=GestureConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    hand_tracking: HandTrackingConfig = field(default_factory=HandTrackingConfig)
    youtube_control: YouTubeControlConfig = field(default_factory=YouTubeControlConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
def _merge(dataclass_instance, raw: dict) -> None:
    """Overwrite dataclass fields with values from a raw dict, ignoring unknown keys."""
    for key, value in raw.items():
        if hasattr(dataclass_instance, key):
            setattr(dataclass_instance, key, value)


def load_settings() -> Settings:
    """
    Load settings from config.yaml.
    Returns a Settings object with defaults for any missing values.
    Never raises — logs a warning and returns defaults if file is broken.
    """
    settings = Settings()
    if not _CONFIG_PATH.exists():
        return settings

    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
    except Exception:
        return settings

    if "gesture" in raw:
        _merge(settings.gesture, raw["gesture"])
    if "camera" in raw:
        _merge(settings.camera, raw["camera"])
    if "hand_tracking" in raw:
        _merge(settings.hand_tracking, raw["hand_tracking"])
    if "youtube_control" in raw:
        _merge(settings.youtube_control, raw["youtube_control"])
    if "logging" in raw:
        _merge(settings.logging, raw["logging"])

    return settings


# Singleton — import and use directly
settings = load_settings()
