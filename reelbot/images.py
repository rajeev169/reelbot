"""Creates one image per scene, keeping the presenter consistent with your reference photo."""
import json
import os
import random
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USAGE = ROOT / "data" / "image_usage.json"
EXTS = {".jpg", ".jpeg", ".png", ".webp"}

CONSISTENCY = ("Keep the exact same woman as in the reference photo: same face, hair and skin tone. "
               "Photorealistic, vertical 9:16 composition, natural look, no text or watermarks. Scene: ")


def generate_images(script, plan, cfg, workdir, dry_run=False):
    workdir = Path(workdir)
    if not dry_run and cfg["images"].get("provider") == "library":
        return _library_pick(len(script["scenes"]), plan, cfg)
    paths = []
    for i, scene in enumerate(script["scenes"]):
        out = workdir / f"scene_{i:02d}.png"
        if dry_run:
            _placeholder(out, i, scene["narration"], cfg)
        else:
            _replicate(out, scene["image_prompt"], cfg)
        paths.append(out)
    return paths


def _replicate(out, image_prompt, cfg):
    import replicate
    import requests

    icfg = cfg["images"]
    ref = Path(icfg["reference_photo"])
    if not ref.exists():
        raise FileNotFoundError(f"Reference photo not found: {ref}. Put your model photo there.")
    inputs = {
        "prompt": CONSISTENCY + image_prompt,
        icfg["image_input_key"]: open(ref, "rb"),
        "aspect_ratio": icfg.get("aspect_ratio", "9:16"),
        **(icfg.get("extra_input") or {}),
    }
    output = replicate.run(icfg["model"], input=inputs)
    if isinstance(output, (list, tuple)):
        output = output[0]
    if hasattr(output, "read"):
        data = output.read()
    else:
        data = requests.get(str(output), timeout=120).content
    out.write_bytes(data)


def _placeholder(out, idx, text, cfg):
    """Offline test image: coloured gradient, so the video pipeline can be tested without APIs."""
    import numpy as np
    from PIL import Image, ImageDraw
    w, h = cfg["video"]["width"], cfg["video"]["height"]
    base = np.array([(200, 120, 150), (120, 170, 200), (150, 200, 140),
                     (210, 170, 110), (160, 130, 200), (120, 190, 180)][idx % 6], dtype=float)
    shade = (0.6 + 0.4 * np.linspace(0, 1, h))[:, None, None]
    arr = (np.ones((h, w, 3)) * base * shade).astype("uint8")
    img = Image.fromarray(arr)
    ImageDraw.Draw(img).text((60, 60), f"scene {idx + 1}", fill=(255, 255, 255))
    img.save(out)


def _library_pick(n, plan, cfg):
    """Free mode: pick `n` images from your own library, least-used first, no repeats inside one reel.

    If assets/library/<category>/ exists (e.g. assets/library/skincare/) and has enough images,
    those are preferred for reels of that category; otherwise the whole library is used.
    """
    lib = ROOT / cfg["images"].get("library_dir", "assets/library")

    def scan(folder):
        return sorted(p for p in folder.rglob("*") if p.suffix.lower() in EXTS) if folder.is_dir() else []

    pool = scan(lib / plan["category"])
    if len(pool) < n:
        pool = scan(lib)
    if not pool:
        raise FileNotFoundError(
            f"No images found in {lib}. Add your model images there (see LIBRARY_PROMPTS.md).")

    usage = json.loads(USAGE.read_text()) if USAGE.exists() else {}
    rng = random.Random()
    ordered = sorted(pool, key=lambda p: (usage.get(str(p.relative_to(ROOT)), 0), rng.random()))
    picked = [ordered[i % len(ordered)] for i in range(n)]  # cycles only if library is tiny
    rng.shuffle(picked)

    for p in picked:
        k = str(p.relative_to(ROOT))
        usage[k] = usage.get(k, 0) + 1
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    USAGE.write_text(json.dumps(usage, indent=2))
    return picked
