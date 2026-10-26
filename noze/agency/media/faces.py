"""Optional speaker locator for 16:9 → 9:16 reframing (``pip install opencv-python-headless``).

Per segment we only need one number — where the speaker's face sits horizontally —
because the editor holds a static crop per segment (cuts hide the jumps, like
ClipsAI's per-speaker crops). Without OpenCV the editor falls back to Claude's
reading of the frame sheets, then to a centre crop.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger("noze.agency.faces")


def available() -> bool:
    try:
        import cv2  # type: ignore  # noqa: F401

        return True
    except ImportError:
        return False


def subject_x(frames: list[Path]) -> float | None:
    """Median horizontal centre (0-1) of the largest face across frames, or None."""
    try:
        import cv2  # type: ignore
    except ImportError:
        return None
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    xs: list[float] = []
    for f in frames:
        img = cv2.imread(str(f))
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24))
        if len(faces):
            x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
            xs.append((x + w / 2) / img.shape[1])
    if not xs:
        return None
    xs.sort()
    return round(xs[len(xs) // 2], 3)
