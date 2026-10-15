# ReelBot — automated health & beauty Shorts (free mode)

Makes **2 reels a day**, a few minutes apart, each with its own topic, script structure,
voice, motion and caption style.

```
topic planner → Gemini (free) writes script → edge-tts voice (free)
              → pictures from YOUR image library (free) → FFmpeg video + captions
              → YouTube upload (private, you approve)
```

## What is tested and what is not
- **Tested here (offline):** topic/template/voice planner, library picker, FFmpeg video + captions,
  history, `--dry-run`, and the full real path with the network calls faked (`python tests/test_offline_e2e.py`).
- **NOT tested here (needs your keys and internet):** the real Gemini call, edge-tts, YouTube upload.
  Expect small fixes on the first real run. Start with `publish_mode: review` and look at the first reels.

## Cost
Free mode costs nothing except your time, **as long as the free tiers stay free**. I can't check their
current limits — read them on ai.google.dev. Gemini's free tier is rate-limited and can change.
Paid options are in `config.yaml` if you ever want them (Claude for scripts, Replicate for fresh images daily).

## Setup (one time)
1. **GitHub:** create a *private* repo and upload this whole folder (keep the `.github` folder).
2. **Image library (free):** open `LIBRARY_PROMPTS.md` — 51 prompts. Paste them, with your model photo, into a free
   image tool that accepts a reference photo, and save the pictures in `assets/library/<category>/`
   (e.g. `assets/library/skincare/`). Aim for 8+ per category, 60+ total. Do a few per day if the tool has a daily limit.
   Use a photo you have rights to.
3. **Gemini key (free):** get an API key at aistudio.google.com, add it as GitHub secret `GEMINI_API_KEY`.
4. **YouTube keys:** follow the steps at the top of `auth_youtube.py` (run once on a PC). In the Google Cloud
   OAuth consent screen, set the app to **In production**, or the token expires after 7 days. Add
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` as secrets.
5. **Test:** *Actions → Make and upload reels → Run workflow* with **dry run** ticked. Then run it for real.

## Daily use
- Runs automatically at 09:00 IST (edit the cron line in `.github/workflows/reels.yml`).
- Default `publish_mode: review` → reels upload as **private**. Open YouTube Studio and set them Public
  (or run the *Approve pending reels* workflow).
- `schedule` mode publishes automatically ~15 min after upload, `gap_minutes` apart. `public` publishes immediately.

## Library tips (important for avoiding a "cloned" look)
- The bot picks the least-used images first and never repeats an image inside one reel.
- Images won't match each sentence exactly. That is the trade-off of free mode, so keep the library varied
  (different rooms, outfits, lighting) and grow it over time.
- Small library = faster repetition. 60 images with 12 used per day repeats in about 5 days; 200 images lasts about 2 weeks.

## Keeping it from looking cloned (topics)
Each reel in a run gets a different category, script structure (7 templates), voice (6), motion style and caption position.
Used topics are tracked in `data/history.json`. The pool in `topics.yaml` is 45 topics — **add more**.
Once all are used, the least recently used topic is reused with a different template and fresh script.

## Rules to respect
- Keep `synthetic_media: true` (YouTube's altered/synthetic label for realistic AI people).
- Scripts avoid cures/treatment claims. Don't edit the prompt to add them.
- YouTube can still demonetise repetitive or low-effort channels. No tool can prevent that;
  varied topics, a growing library and reviewing videos before approving are what help.
- New API projects may have uploads forced to private until audited — see YouTube API docs on audits.
- Daily upload quota: about 6 uploads. 2/day is well within it.

## Commands (local)
```
pip install -r requirements.txt
python -m reelbot run --dry-run      # offline test, no keys needed (needs ffmpeg)
python -m reelbot run --no-upload    # real script + voice + library images, but don't upload
python -m reelbot run                # full run
python -m reelbot approve --all      # publish pending reels
python tools/make_library_prompts.py # rewrite LIBRARY_PROMPTS.md
python tests/test_offline_e2e.py     # offline test of the real path
```
