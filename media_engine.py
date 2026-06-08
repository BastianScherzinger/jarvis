"""
JARVIS Media Engine
Lokale Bild- und Video-Generierung via Hugging Face Diffusers.
Modelle werden beim ersten Aufruf automatisch von HuggingFace heruntergeladen.
"""
from __future__ import annotations
import os
import re
import time
from pathlib import Path

_BASE = Path(__file__).parent
WORKSPACE_IMAGES = _BASE / "workspace" / "media" / "images"
WORKSPACE_VIDEOS = _BASE / "workspace" / "media" / "videos"
for _d in [WORKSPACE_IMAGES, WORKSPACE_VIDEOS]:
    _d.mkdir(parents=True, exist_ok=True)


# ── Modell-Katalog ───────────────────────────────────────────────────────────

IMAGE_MODELS: dict[str, dict] = {
    "sd21": {
        "hf_id":     "stabilityai/stable-diffusion-2-1",
        "name":      "Stable Diffusion 2.1",
        "pipeline":  "StableDiffusionPipeline",
        "size_gb":   2.5,
        "min_vram":  4,
        "default_w": 768,
        "default_h": 768,
        "supports_neg": True,
        "desc":      "Schnell, stabil, ab 4 GB VRAM",
    },
    "sdxl": {
        "hf_id":     "stabilityai/stable-diffusion-xl-base-1.0",
        "name":      "Stable Diffusion XL",
        "pipeline":  "StableDiffusionXLPipeline",
        "size_gb":   6.5,
        "min_vram":  8,
        "default_w": 1024,
        "default_h": 1024,
        "supports_neg": True,
        "desc":      "Hohe Qualität, 1024×1024, 8 GB VRAM",
    },
    "flux-schnell": {
        "hf_id":     "black-forest-labs/FLUX.1-schnell",
        "name":      "FLUX.1 Schnell",
        "pipeline":  "FluxPipeline",
        "size_gb":   15,
        "min_vram":  8,
        "default_w": 1024,
        "default_h": 1024,
        "supports_neg": False,
        "desc":      "Bestes lokales Bildmodell, Apache 2.0",
    },
}

VIDEO_MODELS: dict[str, dict] = {
    "wan-1.3b": {
        "hf_id":     "Wan-AI/Wan2.1-T2V-1.3B",
        "name":      "Wan 2.1 T2V 1.3B",
        "size_gb":   2.7,
        "min_vram":  8,
        "default_frames": 25,
        "default_w": 832,
        "default_h": 480,
        "desc":      "Text-to-Video 480p, ~2 Minuten je Frame",
    },
}

ALL_MODELS: dict[str, dict] = {**IMAGE_MODELS, **VIDEO_MODELS}


# ── Konfiguration aus .env ───────────────────────────────────────────────────

def get_active_image_model() -> str:
    """Liest JARVIS_IMAGE_MODEL aus .env. Default: sd21."""
    content = (_BASE / ".env").read_text(encoding="utf-8", errors="replace") if (_BASE / ".env").exists() else ""
    m = re.search(r"JARVIS_IMAGE_MODEL=(.+)", content)
    return m.group(1).strip() if m else "sd21"


def get_active_video_model() -> str:
    """Liest JARVIS_VIDEO_MODEL aus .env. Default: wan-1.3b."""
    content = (_BASE / ".env").read_text(encoding="utf-8", errors="replace") if (_BASE / ".env").exists() else ""
    m = re.search(r"JARVIS_VIDEO_MODEL=(.+)", content)
    return m.group(1).strip() if m else "wan-1.3b"


# ── Device & Dtype ───────────────────────────────────────────────────────────

def _device_dtype():
    import torch
    if torch.cuda.is_available():
        return "cuda", torch.float16
    try:
        if torch.backends.mps.is_available():
            return "mps", torch.float16
    except Exception:
        pass
    return "cpu", torch.float32


# ── Pipeline Cache ───────────────────────────────────────────────────────────

_cache: dict = {}


def _load_image_pipe(model_key: str):
    if model_key in _cache:
        return _cache[model_key]

    from diffusers import (
        StableDiffusionPipeline,
        StableDiffusionXLPipeline,
        FluxPipeline,
    )
    import torch

    if model_key not in IMAGE_MODELS:
        raise ValueError(f"Unbekanntes Bildmodell: '{model_key}'. Verfügbar: {list(IMAGE_MODELS)}")

    m         = IMAGE_MODELS[model_key]
    dev, dt   = _device_dtype()
    pipe_map  = {
        "StableDiffusionPipeline":   StableDiffusionPipeline,
        "StableDiffusionXLPipeline": StableDiffusionXLPipeline,
        "FluxPipeline":              FluxPipeline,
    }
    Cls = pipe_map[m["pipeline"]]

    pipe = Cls.from_pretrained(m["hf_id"], torch_dtype=dt, use_safetensors=True)
    pipe = pipe.to(dev)

    # Speicher sparen auf schwacher Hardware
    if dev == "cpu":
        try: pipe.enable_attention_slicing()
        except Exception: pass
    elif dev == "cuda":
        try: pipe.enable_xformers_memory_efficient_attention()
        except Exception: pass

    _cache[model_key] = pipe
    return pipe


def _load_video_pipe(model_key: str):
    if model_key in _cache:
        return _cache[model_key]

    from diffusers import WanPipeline
    import torch

    if model_key not in VIDEO_MODELS:
        raise ValueError(f"Unbekanntes Videomodell: '{model_key}'. Verfügbar: {list(VIDEO_MODELS)}")

    m         = VIDEO_MODELS[model_key]
    dev, dt   = _device_dtype()
    pipe      = WanPipeline.from_pretrained(m["hf_id"], torch_dtype=dt)
    pipe      = pipe.to(dev)

    if dev == "cuda":
        try: pipe.enable_model_cpu_offload()
        except Exception: pass

    _cache[model_key] = pipe
    return pipe


# ── Öffentliche API ──────────────────────────────────────────────────────────

def generate_image(
    prompt: str,
    model_key: str | None = None,
    negative_prompt: str = "blurry, low quality, watermark, text, deformed, ugly, bad anatomy",
    steps: int = 25,
    width: int | None = None,
    height: int | None = None,
) -> dict:
    """
    Generiert ein Bild. Gibt dict zurück:
      {'path': str, 'web_url': str, 'model': str, 'prompt': str, 'elapsed': float}
    """
    key = model_key or get_active_image_model()
    m   = IMAGE_MODELS.get(key)
    if m is None:
        raise ValueError(f"Bildmodell '{key}' nicht bekannt. Verfügbar: {list(IMAGE_MODELS)}")

    w    = width  or m["default_w"]
    h    = height or m["default_h"]
    t0   = time.time()
    pipe = _load_image_pipe(key)

    kwargs: dict = {
        "prompt":              prompt,
        "num_inference_steps": min(max(steps, 1), 80),
        "width":               w,
        "height":              h,
    }
    if m["supports_neg"]:
        kwargs["negative_prompt"] = negative_prompt

    result  = pipe(**kwargs)
    image   = result.images[0]
    ts      = time.strftime("%Y%m%d_%H%M%S")
    out     = WORKSPACE_IMAGES / f"img_{ts}.png"
    image.save(str(out))

    return {
        "path":    str(out),
        "web_url": f"/workspace/media/images/{out.name}",
        "model":   m["name"],
        "prompt":  prompt,
        "elapsed": round(time.time() - t0, 1),
    }


def generate_video(
    prompt: str,
    model_key: str | None = None,
    negative_prompt: str = "low quality, blurry, watermark, distorted",
    num_frames: int = 25,
) -> dict:
    """
    Generiert ein Video. Gibt dict zurück:
      {'path': str, 'web_url': str, 'model': str, 'prompt': str, 'elapsed': float}
    """
    key = model_key or get_active_video_model()
    m   = VIDEO_MODELS.get(key)
    if m is None:
        raise ValueError(f"Videomodell '{key}' nicht bekannt. Verfügbar: {list(VIDEO_MODELS)}")

    t0   = time.time()
    pipe = _load_video_pipe(key)
    nf   = min(max(num_frames, 1), 81)

    output = pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        height=m["default_h"],
        width=m["default_w"],
        num_frames=nf,
        guidance_scale=5.0,
    )
    frames = output.frames[0]   # List[PIL.Image]

    ts  = time.strftime("%Y%m%d_%H%M%S")
    out = WORKSPACE_VIDEOS / f"vid_{ts}.mp4"

    try:
        import imageio
        import numpy as np
        writer = imageio.get_writer(str(out), fps=16, codec="libx264", quality=8)
        for f in frames:
            writer.append_data(np.array(f))
        writer.close()
    except Exception:
        # GIF-Fallback wenn MP4-Export fehlschlägt
        out = out.with_suffix(".gif")
        frames[0].save(
            str(out),
            save_all=True,
            append_images=frames[1:],
            duration=62,
            loop=0,
        )

    suffix = out.suffix
    return {
        "path":    str(out),
        "web_url": f"/workspace/media/videos/{out.name}",
        "model":   m["name"],
        "prompt":  prompt,
        "elapsed": round(time.time() - t0, 1),
    }


def get_status() -> dict:
    """Gibt Konfigurationsstatus zurück."""
    img_key = get_active_image_model()
    vid_key = get_active_video_model()
    return {
        "image_model":     IMAGE_MODELS.get(img_key, {}).get("name", img_key),
        "image_model_key": img_key,
        "video_model":     VIDEO_MODELS.get(vid_key, {}).get("name", vid_key),
        "video_model_key": vid_key,
        "diffusers_ok":    _check_diffusers(),
    }


def _check_diffusers() -> bool:
    try:
        import diffusers, torch  # noqa: F401
        return True
    except ImportError:
        return False
