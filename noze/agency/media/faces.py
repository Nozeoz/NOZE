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
        import cv2  # type: ignore

        return hasattr(cv2, "CascadeClassifier")
    except ImportError:
        return False


def _largest_faces(frames: list[Path]) -> list[tuple[float, float, float, float, float]]:
    """(x, y, w, h, frame aspect) of the largest face per frame, as fractions of the frame.
    Use frames ≥ 1280 px wide: a facecam face is only ~4-5% of a 1080p frame."""
    try:
        import cv2  # type: ignore
    except ImportError:
        return []
    if not hasattr(cv2, "CascadeClassifier"):  # OpenCV 5 dropped the Haar cascades
        return []
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    out = []
    for f in frames:
        img = cv2.imread(str(f))
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(18, 18))
        if len(faces):
            x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
            H, W = img.shape[:2]
            out.append((x / W, y / H, w / W, h / H, W / H))
    return out


def facecam_box(frames: list[Path]) -> dict[str, float] | None:
    """Estimate a streamer's facecam rectangle (fractions) when a small face sits in the
    same spot across frames — the overlay you must keep visible on gaming clips.
    Returns None for full-frame cameras (talking heads) or when no stable face is found."""
    faces = _largest_faces(frames)
    if len(faces) < max(2, len(frames) // 3):
        return None
    faces.sort(key=lambda f: f[2])
    fx, fy, fw, fh, aspect = faces[len(faces) // 2]
    cx = sorted(f[0] + f[2] / 2 for f in faces)[len(faces) // 2]
    cy = sorted(f[1] + f[3] / 2 for f in faces)[len(faces) // 2]
    spread = max(abs((f[0] + f[2] / 2) - cx) for f in faces)
    if fw > 0.2 or spread > 0.08:  # big face = the camera *is* the shot; moving face = not an overlay
        return None
    # Facecams are 16:9 webcams with the head ~4-5 face-widths across, face a bit above centre.
    # Err on the inside: a crop slightly inside the cam beats one that shows game pixels.
    w = min(1.0, fw * 4.3)
    h = min(1.0, w * aspect * 9 / 16)
    x = min(max(cx - w / 2, 0.0), 1.0 - w)
    y = min(max(cy - h * 0.55, 0.0), 1.0 - h)
    return {k: round(float(v), 3) for k, v in (("x", x), ("y", y), ("w", w), ("h", h))}


def subject_x(frames: list[Path]) -> float | None:
    """Median horizontal centre (0-1) of the largest face across frames, or None."""
    try:
        import cv2  # type: ignore
    except ImportError:
        return None
    if not hasattr(cv2, "CascadeClassifier"):  # OpenCV 5 dropped the Haar cascades
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
