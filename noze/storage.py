"""Where the bank keeps full-size files.

Content-addressed (sha256) so the same file saved twice costs nothing. Two
backends:

* local  — a folder on disk (default). Point NOZE_DATA_DIR at an external
           drive / NAS, or sync it anywhere with rclone.
* s3     — any S3-compatible bucket: Cloudflare R2 (10 GB free, no egress
           fees), Backblaze B2, Wasabi, MinIO, AWS S3.

Keys starting with "file:" point at files NOZE indexed in place
(`noze import-folder --link`) instead of copying.
"""

from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path
from typing import BinaryIO

from .config import Settings


def make_key(sha256: str, ext: str) -> str:
    ext = ext if not ext or ext.startswith(".") else "." + ext
    return f"{sha256[:2]}/{sha256[2:4]}/{sha256}{ext.lower()}"


def guess_ext(mime: str | None, url: str = "") -> str:
    path = url.split("?", 1)[0].split("#", 1)[0]
    suffix = Path(path).suffix.lower()
    if 1 < len(suffix) <= 6 and suffix[1:].isalnum():
        return suffix
    if mime:
        mime = mime.split(";", 1)[0].strip().lower()
        special = {"image/jpeg": ".jpg", "image/svg+xml": ".svg", "audio/mpeg": ".mp3", "video/quicktime": ".mov",
                   "application/json": ".json", "application/zip": ".zip", "font/woff2": ".woff2",
                   "font/ttf": ".ttf", "image/webp": ".webp", "video/mp4": ".mp4"}
        if mime in special:
            return special[mime]
        ext = mimetypes.guess_extension(mime)
        if ext:
            return ext
    return ".bin"


class Storage:
    name = "base"

    def put_file(self, src: Path, sha256: str, ext: str, mime: str) -> str:
        raise NotImplementedError

    def has(self, key: str) -> bool:
        raise NotImplementedError

    def local_path(self, key: str) -> Path | None:
        if key.startswith("file:"):
            p = Path(key[5:])
            return p if p.exists() else None
        return None

    def url(self, key: str, expires: int = 3600) -> str | None:
        return None

    def open(self, key: str) -> BinaryIO:
        p = self.local_path(key)
        if p is None:
            raise FileNotFoundError(key)
        return p.open("rb")

    def delete(self, key: str) -> None:
        pass

    def usage(self) -> tuple[int, int]:
        return (0, 0)


class LocalStorage(Storage):
    name = "local"

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("invalid storage key")
        return p

    def put_file(self, src: Path, sha256: str, ext: str, mime: str) -> str:
        key = make_key(sha256, ext)
        dst = self._path(key)
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_suffix(dst.suffix + ".part")
            shutil.copyfile(src, tmp)
            tmp.replace(dst)
        return key

    def has(self, key: str) -> bool:
        if key.startswith("file:"):
            return super().local_path(key) is not None
        return self._path(key).exists()

    def local_path(self, key: str) -> Path | None:
        if key.startswith("file:"):
            return super().local_path(key)
        p = self._path(key)
        return p if p.exists() else None

    def delete(self, key: str) -> None:
        if key.startswith("file:"):
            return
        p = self._path(key)
        if p.exists():
            p.unlink()

    def usage(self) -> tuple[int, int]:
        count = size = 0
        for p in self.root.rglob("*"):
            if p.is_file():
                count += 1
                size += p.stat().st_size
        return count, size


class S3Storage(Storage):
    name = "s3"

    def __init__(self, settings: Settings):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError("NOZE_STORAGE=s3 needs boto3: pip install 'noze[s3]'") from exc

        if not settings.s3_bucket:
            raise RuntimeError("NOZE_S3_BUCKET is required for NOZE_STORAGE=s3")
        self.bucket = settings.s3_bucket
        self.prefix = settings.s3_prefix or ""
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint or None,
            aws_access_key_id=settings.s3_access_key or None,
            aws_secret_access_key=settings.s3_secret_key or None,
            region_name=settings.s3_region or "auto",
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    def _k(self, key: str) -> str:
        return f"{self.prefix}{key}"

    def put_file(self, src: Path, sha256: str, ext: str, mime: str) -> str:
        key = make_key(sha256, ext)
        if not self.has(key):
            self.client.upload_file(str(src), self.bucket, self._k(key), ExtraArgs={"ContentType": mime or "application/octet-stream"})
        return key

    def has(self, key: str) -> bool:
        if key.startswith("file:"):
            return super().local_path(key) is not None
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._k(key))
            return True
        except Exception:
            return False

    def url(self, key: str, expires: int = 3600) -> str | None:
        if key.startswith("file:"):
            return None
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": self._k(key)}, ExpiresIn=expires
        )

    def open(self, key: str) -> BinaryIO:
        if key.startswith("file:"):
            return super().open(key)
        return self.client.get_object(Bucket=self.bucket, Key=self._k(key))["Body"]

    def delete(self, key: str) -> None:
        if not key.startswith("file:"):
            self.client.delete_object(Bucket=self.bucket, Key=self._k(key))

    def usage(self) -> tuple[int, int]:
        count = size = 0
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
            for obj in page.get("Contents", []):
                count += 1
                size += obj.get("Size", 0)
        return count, size


def get_storage(settings: Settings) -> Storage:
    if settings.storage == "s3":
        return S3Storage(settings)
    return LocalStorage(settings.data_dir / "blobs")
