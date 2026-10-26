"""Delivery and publishing.

Always: the approved clip + post copy land in ``agency/deliveries/<campaign>/<date>/``.
Optional targets (``AGENCY_PUBLISH_TARGETS``, comma separated):

- ``rclone``  — copy the delivery folder to any rclone remote (Google Drive, Dropbox,
  OneDrive, S3/R2…): set ``AGENCY_RCLONE_REMOTE=gdrive:Clips``
- ``webhook`` — post a summary to Discord / Slack / any JSON webhook (``AGENCY_WEBHOOK_URL``)
  or Telegram (``TELEGRAM_BOT_TOKEN`` + ``TELEGRAM_CHAT_ID``)
- ``youtube`` — upload as a Short to *your* channel (YouTube Data API, OAuth refresh token;
  privacy from ``AGENCY_YOUTUBE_PRIVACY``, default private)
- ``tiktok``  — send to *your* TikTok inbox as a draft you finish in the app (Content
  Posting API ``video.upload``; TikTok does not allow agency tools to direct-post)

Platform uploads happen only when ``AGENCY_AUTO_PUBLISH=1`` or when you run
``noze agency publish <clip>`` — posting is outward-facing, so the default is "ready to post".
Campaign submission (Whop / Content Rewards / Vyro …) stays manual: those platforms have no
submission API for CPM campaigns and forbid automation; the report gives you the link to paste.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from .context import AgencyContext
from .roles.editor import comply_post

log = logging.getLogger("noze.agency.publish")

PLATFORM_TARGETS = ("youtube", "tiktok")


def slug(text: str, n: int = 50) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text or "clip").strip("-").lower()
    return s[:n] or "clip"


def post_text(post: dict[str, Any]) -> str:
    caption = (post.get("caption") or "").strip()
    tags = " ".join(t for t in post.get("hashtags") or [] if t and t.lower() not in caption.lower())
    return f"{caption}\n\n{tags}".strip()


class Publisher:
    def __init__(self, ax: AgencyContext):
        self.ax = ax
        self.cfg = ax.cfg
        self.store = ax.store

    def deliver(self, job: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
        data = job.get("data") or {}
        render = Path(data["render_path"])
        campaign = self.store.get_campaign(job["campaign_id"]) if job.get("campaign_id") else None
        plan = (self.store.artifact(job["id"], "plan") or {}).get("data") or {}
        post = {**(plan.get("post") or {}), **{k: v for k, v in (data.get("post") or {}).items() if v}}
        post = comply_post(post, brief, job.get("title") or "")  # the manager's copy can't drop the rules
        folder = (self.cfg.deliveries_dir / slug(campaign["name"] if campaign else "own-content", 40)
                  / time.strftime("%Y-%m-%d"))
        folder.mkdir(parents=True, exist_ok=True)
        base = f"{job['id']:05d}_{slug(post.get('title') or job.get('title') or 'clip')}"
        video = folder / f"{base}.mp4"
        shutil.copyfile(render, video)
        caption_file = folder / f"{base}.txt"
        lines = [post.get("title") or job.get("title") or "", "", post_text(post)]
        submit = ((brief.get("submission") or {}).get("url") or "")
        if submit:
            lines += ["", f"Submit the posted link at: {submit}"]
        caption_file.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        self.store.add_publication(job["id"], "folder", "done", url=str(video))
        result = {"video": str(video), "caption_file": str(caption_file), "folder": str(folder), "targets": ["folder"]}
        for target in self.cfg.publish_targets:
            target = target.strip().lower()
            if target in ("", "folder"):
                continue
            if target in PLATFORM_TARGETS and not self.cfg.auto_publish:
                self.store.add_publication(job["id"], target, "ready", info={"note": "run `noze agency publish`"})
                result["targets"].append(f"{target} (ready)")
                continue
            try:
                info = self.publish(job["id"], target, video=video, post=post, folder=folder)
                result["targets"].append(f"{target} ({info.get('status', 'done')})")
            except Exception as exc:  # one failing target must not undo the delivery
                log.warning("publish to %s failed: %s", target, exc)
                self.store.add_publication(job["id"], target, "failed", info={"error": str(exc)[:500]})
                self.store.log(job["id"], "manager", "publish_failed", f"{target}: {exc}")
                result["targets"].append(f"{target} (failed)")
        return result

    def publish(self, job_id: int, target: str, *, video: Path | None = None, post: dict[str, Any] | None = None,
                folder: Path | None = None) -> dict[str, Any]:
        job = self.store.get_job(job_id)
        if not job:
            raise ValueError(f"no job {job_id}")
        data = job.get("data") or {}
        video = video or Path(data.get("final_path") or data.get("render_path") or "")
        if not video.exists():
            raise ValueError("clip has no rendered file yet")
        plan = (self.store.artifact(job_id, "plan") or {}).get("data") or {}
        post = post or {**(plan.get("post") or {}), **{k: v for k, v in (data.get("post") or {}).items() if v}}
        title = (post.get("title") or job.get("title") or "clip")[:95]
        if target == "rclone":
            info = self._rclone(folder or video.parent)
        elif target == "webhook":
            info = self.notify(f"✅ Clip ready: {title}\n{post_text(post)[:1500]}\nFile: {video}")
        elif target == "youtube":
            info = self._youtube(video, title, post)
        elif target == "tiktok":
            info = self._tiktok_inbox(video)
        else:
            raise ValueError(f"unknown publish target {target!r}")
        self.store.add_publication(job_id, target, info.get("status", "done"), url=info.get("url", ""),
                                   remote_id=info.get("id", ""), info=info)
        return info

    # -- targets --------------------------------------------------------------------------------------
    def _rclone(self, folder: Path) -> dict[str, Any]:
        remote = self.cfg.rclone_remote
        if not remote or not shutil.which("rclone"):
            raise RuntimeError("set AGENCY_RCLONE_REMOTE and install rclone (https://rclone.org)")
        rel = folder.relative_to(self.cfg.deliveries_dir) if folder.is_relative_to(self.cfg.deliveries_dir) else folder.name
        dest = f"{remote.rstrip('/')}/{rel}"
        proc = subprocess.run(["rclone", "copy", str(folder), dest], capture_output=True, text=True, timeout=3600)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip()[-400:])
        return {"status": "done", "url": dest}

    def notify(self, text: str) -> dict[str, Any]:
        """Send a message to the configured webhook / Telegram chat (reports and alerts use this too)."""
        sent = []
        url = self.cfg.key("AGENCY_WEBHOOK_URL")
        with httpx.Client(timeout=20.0) as client:
            if url:
                if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
                    payload: dict[str, Any] = {"content": text[:1990]}
                elif "hooks.slack.com" in url:
                    payload = {"text": text[:39000]}
                else:
                    payload = {"text": text}
                r = client.post(url, json=payload)
                r.raise_for_status()
                sent.append("webhook")
            token, chat = self.cfg.key("TELEGRAM_BOT_TOKEN"), self.cfg.key("TELEGRAM_CHAT_ID")
            if token and chat:
                r = client.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                json={"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True})
                r.raise_for_status()
                sent.append("telegram")
        if not sent:
            raise RuntimeError("set AGENCY_WEBHOOK_URL or TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID")
        return {"status": "done", "sent": sent}

    def _youtube_token(self) -> str:
        cid, secret, refresh = (self.cfg.key("YOUTUBE_CLIENT_ID"), self.cfg.key("YOUTUBE_CLIENT_SECRET"),
                                self.cfg.key("YOUTUBE_REFRESH_TOKEN"))
        if not (cid and secret and refresh):
            raise RuntimeError("set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN "
                               "(see docs/AGENCY.md → YouTube)")
        r = httpx.post("https://oauth2.googleapis.com/token", timeout=20.0,
                       data={"client_id": cid, "client_secret": secret, "refresh_token": refresh,
                             "grant_type": "refresh_token"})
        r.raise_for_status()
        return r.json()["access_token"]

    def _youtube(self, video: Path, title: str, post: dict[str, Any]) -> dict[str, Any]:
        token = self._youtube_token()
        privacy = os.environ.get("AGENCY_YOUTUBE_PRIVACY", "private")
        body = {
            "snippet": {"title": title if "#shorts" in title.lower() else f"{title[:85]} #Shorts",
                        "description": post_text(post)[:4900],
                        "tags": [t.lstrip("#") for t in post.get("hashtags") or []][:30], "categoryId": "22"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        }
        size = video.stat().st_size
        with httpx.Client(timeout=httpx.Timeout(600.0, connect=20.0)) as client:
            init = client.post("https://www.googleapis.com/upload/youtube/v3/videos",
                               params={"uploadType": "resumable", "part": "snippet,status"},
                               headers={"Authorization": f"Bearer {token}", "X-Upload-Content-Length": str(size),
                                        "X-Upload-Content-Type": "video/mp4"}, json=body)
            init.raise_for_status()
            session = init.headers["Location"]
            with video.open("rb") as fh:  # streamed, not read into memory
                up = client.put(session, content=fh, headers={"Content-Type": "video/mp4",
                                                               "Content-Length": str(size)})
            up.raise_for_status()
            vid = up.json().get("id", "")
        return {"status": "uploaded", "id": vid, "url": f"https://youtube.com/shorts/{vid}" if vid else "",
                "privacy": privacy}

    def _tiktok_inbox(self, video: Path) -> dict[str, Any]:
        token = self.cfg.key("TIKTOK_ACCESS_TOKEN")
        if not token:
            raise RuntimeError("set TIKTOK_ACCESS_TOKEN (scope video.upload) — see docs/AGENCY.md → TikTok")
        size = video.stat().st_size
        chunk = size if size <= 64 * 1024 * 1024 else 32 * 1024 * 1024
        total = max(1, size // chunk)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
        with httpx.Client(timeout=httpx.Timeout(600.0, connect=20.0)) as client:
            r = client.post("https://open.tiktokapis.com/v2/post/publish/inbox/video/init/", headers=headers,
                            json={"source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk,
                                                  "total_chunk_count": total}})
            r.raise_for_status()
            data = r.json().get("data") or {}
            upload_url, publish_id = data.get("upload_url"), data.get("publish_id")
            if not upload_url:
                raise RuntimeError(f"TikTok init failed: {json.dumps(r.json())[:300]}")
            with video.open("rb") as fh:
                for i in range(total):
                    start = i * chunk
                    end = size - 1 if i == total - 1 else start + chunk - 1
                    fh.seek(start)
                    body = fh.read(end - start + 1)
                    up = client.put(upload_url, content=body,
                                    headers={"Content-Type": "video/mp4", "Content-Length": str(len(body)),
                                             "Content-Range": f"bytes {start}-{end}/{size}"})
                    up.raise_for_status()
        return {"status": "in TikTok inbox (finish posting in the app)", "id": publish_id or ""}
