import io

import pytest
from PIL import Image

from noze.config import Settings
from noze.context import Context

BASE_ENV = {"NOZE_EMBEDDER": "hash", "NOZE_WORKER": "0"}


@pytest.fixture(autouse=True)
def _no_real_claude(monkeypatch):
    """No test may reach the real brain: a logged-in `claude` CLI or an API key on the dev machine would
    otherwise turn any code path that reads the process env into a paid / quota-burning call."""
    monkeypatch.setenv("AGENCY_LLM", "off")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def make_settings(tmp_path, **env) -> Settings:
    return Settings.load(data_dir=tmp_path / "bank", env={**BASE_ENV, **env}, dotenv=False)


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def ctx(settings):
    c = Context(settings)
    yield c
    c.db.close()


def png_bytes(color=(200, 30, 40), size=(64, 40), stripes=True) -> bytes:
    img = Image.new("RGB", size, color)
    if stripes:  # give it some structure so perceptual hashes differ between images
        for x in range(0, size[0], 8):
            for y in range(size[1]):
                img.putpixel((x, y), (255 - color[0], 255 - color[1], 255 - color[2]))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
