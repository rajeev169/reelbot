"""ReelBot entry point.

  python -m reelbot run                 # make + upload today's reels
  python -m reelbot run --dry-run       # offline test: placeholder images + tone audio, no APIs, no upload
  python -m reelbot run --no-upload     # make the videos but don't upload
  python -m reelbot approve --all       # make every pending (private) reel public
"""
import argparse
import datetime as dt
import json
import re
import shutil
import sys
import time
from pathlib import Path

import yaml

from . import images, planner, scriptgen, video, voice

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "history.json"


def load_cfg():
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def load_history():
    if HISTORY.exists():
        return json.loads(HISTORY.read_text(encoding="utf-8")).get("reels", [])
    return []


def save_history(reels):
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps({"reels": reels}, indent=2, ensure_ascii=False), encoding="utf-8")


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def make_one(plan, cfg, dry_run, stamp):
    """Script -> voice (check length) -> images -> video. Returns (video_path, script)."""
    max_s = cfg["video"]["max_seconds"]
    workdir = ROOT / "out" / f"work_{stamp}"
    workdir.mkdir(parents=True, exist_ok=True)

    script = audios = durations = None
    for attempt in range(3):
        script = scriptgen.generate(plan, cfg, dry_run=dry_run)
        audios, durations = voice.synthesize(script, plan, workdir, dry_run=dry_run)
        total = sum(durations) + video.PAD * len(durations)
        if total <= max_s:
            break
        print(f"  script too long ({total:.0f}s > {max_s}s), regenerating ({attempt + 1}/3)")
    else:
        raise RuntimeError("Could not get a script short enough for a Short")

    imgs = images.generate_images(script, plan, cfg, workdir, dry_run=dry_run)
    out = ROOT / "out" / f"{stamp}_{slug(plan['topic'])}.mp4"
    video.build_reel(script, plan, imgs, audios, durations, cfg, workdir, out)
    shutil.rmtree(workdir, ignore_errors=True)
    return out, script


def cmd_run(args):
    cfg = load_cfg()
    count = args.count or cfg["reels_per_run"]
    gap = cfg["gap_minutes"] * 60
    mode = cfg["publish_mode"]
    history = load_history()
    today = dt.date.today().isoformat()
    topics = planner.load_topics(ROOT / "topics.yaml")
    plans = planner.plan_run(topics, history, count, today)

    last_public = 0.0
    for i, plan in enumerate(plans):
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{i + 1}"
        print(f"[{i + 1}/{count}] {plan['category']} | {plan['topic']} | {plan['template']} | {plan['voice']}")
        record = {
            "id": stamp, "date": today, "category": plan["category"], "topic": plan["topic"],
            "template": plan["template"], "voice": plan["voice"], "status": "made",
        }
        try:
            path, script = make_one(plan, cfg, args.dry_run, stamp)
            record.update(title=script["title"], file=str(path.relative_to(ROOT)))
            print(f"  video ready: {path.name}")

            if args.dry_run or args.no_upload:
                record["status"] = "not_uploaded"
            else:
                from . import youtube
                publish_at = None
                privacy = "private"
                if mode == "schedule":
                    t = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15 + i * cfg["gap_minutes"])
                    publish_at = t.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                elif mode == "public":
                    wait = last_public + gap - time.time()
                    if wait > 0:
                        print(f"  waiting {wait:.0f}s to keep reels {cfg['gap_minutes']} min apart")
                        time.sleep(wait)
                    privacy = "public"
                vid = youtube.upload(path, script, cfg, privacy=privacy, publish_at=publish_at)
                last_public = time.time()
                record.update(video_id=vid, publish_at=publish_at)
                record["status"] = {"review": "pending_review", "schedule": "scheduled", "public": "public"}[mode]
                print(f"  uploaded: https://youtube.com/watch?v={vid} ({record['status']})")
        except Exception as e:  # keep going so one failure doesn't lose the other reel
            record["status"] = "failed"
            record["error"] = str(e)[:300]
            print(f"  FAILED: {e}", file=sys.stderr)
        if not args.dry_run:  # dry runs must not pollute the real topic history
            history.append(record)
            save_history(history)


def cmd_approve(args):
    from . import youtube
    cfg = load_cfg()
    history = load_history()
    pending = [r for r in history if r.get("status") == "pending_review" and r.get("video_id")]
    if args.ids:
        pending = [r for r in pending if r["video_id"] in args.ids]
    elif not args.all:
        for r in pending:
            print(f"{r['video_id']}  {r.get('title')}")
        print("\nUse --all or --ids ID [ID ...] to publish.")
        return
    for r in pending:
        youtube.make_public(r["video_id"], cfg)
        r["status"] = "public"
        print(f"published {r['video_id']}  {r.get('title')}")
    save_history(history)


def main(argv=None):
    p = argparse.ArgumentParser(prog="reelbot")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--count", type=int)
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--no-upload", action="store_true")
    r.set_defaults(fn=cmd_run)
    a = sub.add_parser("approve")
    a.add_argument("--all", action="store_true")
    a.add_argument("--ids", nargs="*")
    a.set_defaults(fn=cmd_approve)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
