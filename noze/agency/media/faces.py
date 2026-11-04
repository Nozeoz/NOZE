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


def faces_in_band(frames: list[tuple[Path, int]]) -> list[tuple[int, int, int, int] | None] | None:
    """The face per OUTPUT frame, inside the top ``band`` px (the stacked layout's cam band), as (x, y, w, h) in
    output-frame pixels; None for a frame without a face. Returns None (not a list) when OpenCV cannot detect
    at all, so "no detector" is never mistaken for "no face". ``frames`` = (image, band px).

    Haar is brittle on a streamer looking down at the game (glasses, mic, tilted head): the same face is found
    or missed, and boxed at 120 or 215 px, depending on where the crop ends. So each frame is scanned at a few
    crop heights, detections whose centre is outside the band are dropped, and the median-size box is returned.
    ponytail: Haar, not a DNN; swap in a real face detector if the box-size noise matters."""
    try:
        import cv2  # type: ignore
    except ImportError:
        return None
    if not hasattr(cv2, "CascadeClassifier"):
        return None
    # alt2 holds on frames where `default` returns nothing at all
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml")
    if cascade.empty():
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    out: list[tuple[int, int, int, int] | None] = []
    for f, band in frames:
        img = cv2.imread(str(f))
        if img is None:
            out.append(None)
            continue
        m = max(24, int(img.shape[1] * 0.04))  # a face under 4% of the frame width is a speck, not the streamer
        found: list[tuple[int, int, int, int]] = []
        for k in (1.0, 1.15, 1.3, 1.5):
            gray = cv2.cvtColor(img[: min(max(int(band * k), 1), img.shape[0])], cv2.COLOR_BGR2GRAY)
            for x, y, w, h in cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(m, m)):
                if y + h / 2 < band:
                    found.append((int(x), int(y), int(w), int(h)))
        found.sort(key=lambda r: r[2] * r[3])
        out.append(found[len(found) // 2] if found else None)
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
    box = {k: round(float(v), 3) for k, v in (("x", x), ("y", y), ("w", w), ("h", h))}
    # where the face sits inside that cam (fractions of the cam): the reviewer checks its size and the eye line
    box["face"] = {k: round(min(max(float(v), 0.0), 1.0), 3) for k, v in (
        ("x", (cx - fw / 2 - x) / w), ("y", (cy - fh / 2 - y) / h), ("w", fw / w), ("h", fh / h))}
    return box


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
