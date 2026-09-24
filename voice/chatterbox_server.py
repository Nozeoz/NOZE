"""
Server TTS lokal pakai Chatterbox (Resemble AI, MIT license).
Butuh GPU NVIDIA (CUDA) biar cepat; di CPU bisa jalan tapi lambat.

    cd voice
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    python chatterbox_server.py

Taruh rekaman suara referensi (10–20 detik, bersih, suara yang kamu PUNYA HAK-nya)
di voice/ref.wav supaya Jarvis bicara dengan warna suara itu.
"""
import io
import os

import torch
import torchaudio as ta
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from chatterbox.mtl_tts import ChatterboxMultilingualTTS

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.environ.get("CHATTERBOX_REF", os.path.join(HERE, "ref.wav"))
# Indonesian isn't an official Chatterbox language yet; Malay ("ms") is the closest.
LANG = os.environ.get("CHATTERBOX_LANG", "ms")
# Lower exaggeration + cfg_weight = calmer, softer, slower delivery.
EXAGGERATION = float(os.environ.get("CHATTERBOX_EXAGGERATION", "0.35"))
CFG_WEIGHT = float(os.environ.get("CHATTERBOX_CFG", "0.4"))

device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
print(f"[chatterbox] loading model on {device}…")
model = ChatterboxMultilingualTTS.from_pretrained(device=device)
print("[chatterbox] ready")

app = FastAPI()


class TTSRequest(BaseModel):
    text: str


@app.post("/tts")
def tts(req: TTSRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "text kosong")
    kwargs = dict(language_id=LANG, exaggeration=EXAGGERATION, cfg_weight=CFG_WEIGHT)
    if os.path.exists(REF):
        kwargs["audio_prompt_path"] = REF
    wav = model.generate(text, **kwargs)
    buf = io.BytesIO()
    ta.save(buf, wav.cpu(), model.sr, format="wav")
    return Response(buf.getvalue(), media_type="audio/wav")


@app.get("/health")
def health():
    return {"ok": True, "device": device, "ref": os.path.exists(REF), "lang": LANG}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8008")))
