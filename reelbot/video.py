"""Builds the vertical reel with FFmpeg: moving images + voice + burned-in captions."""
import math
import subprocess
from pathlib import Path

PAD = 0.3  # seconds of breathing room after each scene's speech


def _run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(map(str, cmd))}\n{r.stderr[-1500:]}")


def _zoompan(motion, frames, w, h, fps):
    if motion == "zoom_out":
        z, x, y = "if(eq(on,1),1.15,max(zoom-0.0007,1.0))", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif motion == "pan":
        z, x, y = "1.12", f"(iw-iw/zoom)*on/{frames}", "ih/2-(ih/zoom/2)"
    else:  # zoom_in
        z, x, y = "min(zoom+0.0007,1.15)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={fps}"


def _ass_time(t):
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _chunks(text, size=4):
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)] or [text]


def _write_ass(path, script, durations, caption_pos, w, h):
    align, margin = {"top": (8, 300), "center": (5, 0), "bottom": (2, 330)}.get(caption_pos, (2, 330))
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
        "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Cap,DejaVu Sans,74,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,5,1,{align},70,70,{margin},1",
        "", "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    t0 = 0.0
    for scene, dur in zip(script["scenes"], durations):
        speech = dur  # captions only during the speech part
        chunks = _chunks(scene["narration"])
        total_chars = sum(len(c) for c in chunks) or 1
        t = t0
        for c in chunks:
            span = speech * len(c) / total_chars
            lines.append(f"Dialogue: 0,{_ass_time(t)},{_ass_time(t + span)},Cap,,0,0,0,,{c}")
            t += span
        t0 += dur + PAD
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def build_reel(script, plan, images, audios, durations, cfg, workdir, out_path):
    workdir = Path(workdir)
    w, h, fps = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"]
    big_w, big_h = int(w * 1.5), int(h * 1.5)

    clips = []
    for i, (img, aud, dur) in enumerate(zip(images, audios, durations)):
        total = dur + PAD
        frames = math.ceil(total * fps)
        clip = workdir / f"clip_{i:02d}.mp4"
        vf = (f"scale={big_w}:{big_h}:force_original_aspect_ratio=increase,crop={big_w}:{big_h},"
              f"{_zoompan(plan['motion'], frames, w, h, fps)},format=yuv420p")
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(img), "-i", str(aud),
              "-vf", vf, "-af", f"apad=pad_dur={PAD}", "-t", f"{total:.3f}", "-r", str(fps),
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
              "-c:a", "aac", "-ar", "44100", "-ac", "2", str(clip)])
        clips.append(clip)

    listing = workdir / "clips.txt"
    listing.write_text("\n".join(f"file '{c.name}'" for c in clips))
    joined = workdir / "joined.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", "clips.txt", "-c", "copy", joined.name], cwd=workdir)

    _write_ass(workdir / "captions.ass", script, durations, plan["caption"], w, h)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined.name, "-vf", "ass=captions.ass",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
          "-c:a", "copy", "-movflags", "+faststart", str(Path(out_path).resolve())], cwd=workdir)
    return out_path
