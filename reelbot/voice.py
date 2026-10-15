"""Text-to-speech per scene. Per-scene audio gives exact timing for images and captions."""
import asyncio
import subprocess
from pathlib import Path


def audio_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def synthesize(script, plan, workdir, dry_run=False):
    """Returns (list_of_audio_paths, list_of_durations_seconds)."""
    workdir = Path(workdir)
    paths, durations = [], []
    for i, scene in enumerate(script["scenes"]):
        text = scene["narration"].strip()
        if dry_run:
            out = workdir / f"voice_{i:02d}.wav"
            _tone(out, max(1.5, len(text.split()) * 0.38))
        else:
            out = workdir / f"voice_{i:02d}.mp3"
            asyncio.run(_edge(text, plan["voice"], plan["rate"], out))
        paths.append(out)
        durations.append(audio_duration(out))
    return paths, durations


async def _edge(text, voice, rate, out):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out))


def _tone(out, seconds):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"sine=frequency=220:duration={seconds:.2f}", str(out)],
        check=True)
