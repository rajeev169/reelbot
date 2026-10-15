"""Plans each day's reels so no two look or sound alike.

Every reel gets its own: category, topic, angle/structure template, voice,
speaking rate, motion style and caption style. Topics used recently are
skipped, and reels in the same run never share a category, template or voice.
"""
import random
from pathlib import Path

import yaml

# Each template changes the *structure* of the script, not just the topic.
TEMPLATES = [
    {"name": "myth_vs_fact", "scenes": 6, "motion": "zoom_in", "caption": "bottom",
     "guide": "Open by naming a common myth about the topic, then correct it with 2-3 clear facts, end with one habit to try."},
    {"name": "three_quick_tips", "scenes": 6, "motion": "pan", "caption": "center",
     "guide": "Hook with a promise of 3 quick tips. Give each tip in one or two short sentences. Close with which tip to start today."},
    {"name": "morning_routine_walkthrough", "scenes": 7, "motion": "zoom_out", "caption": "bottom",
     "guide": "First-person walkthrough of a routine, step by step, in the order you would actually do it. Warm and conversational."},
    {"name": "mistake_to_avoid", "scenes": 5, "motion": "zoom_in", "caption": "center",
     "guide": "Start with 'the one mistake' people make, explain why it happens, show the better way, finish with a simple swap."},
    {"name": "question_and_answer", "scenes": 5, "motion": "pan", "caption": "top",
     "guide": "Ask a question a viewer might have in the first line, then answer it in short, friendly steps with one memorable takeaway."},
    {"name": "before_you_try_this", "scenes": 6, "motion": "zoom_out", "caption": "bottom",
     "guide": "A short 'what I wish I knew' style piece: what to know first, what to start with, what to avoid, one easy first step."},
    {"name": "simple_checklist", "scenes": 6, "motion": "zoom_in", "caption": "center",
     "guide": "A quick checklist the viewer can follow right now. Number the items out loud. End by asking which one they will do first."},
]

VOICES = [
    ("en-US-AriaNeural", "+0%"),
    ("en-US-JennyNeural", "+4%"),
    ("en-US-AvaNeural", "-2%"),
    ("en-GB-SoniaNeural", "+0%"),
    ("en-AU-NatashaNeural", "+3%"),
    ("en-IN-NeerjaNeural", "+0%"),
]

LOOKS = [
    "soft natural window light, bright airy bathroom",
    "warm golden-hour light in a cosy bedroom",
    "clean minimal white studio, soft shadows",
    "fresh green kitchen with morning sunlight",
    "calm spa-like room with neutral tones",
    "cosy living room, warm lamp light",
]


def load_topics(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def plan_run(topics, history, count, today, rng=None):
    """Return `count` plans. `history` is the list of past reel records."""
    rng = rng or random.Random(f"{today}-{len(history)}")
    last_used = {r.get("topic"): i for i, r in enumerate(history)}  # topic -> index of last use
    recent_cats = [r.get("category") for r in history[-3:]]
    last_template = history[-1].get("template") if history else None
    last_voice = history[-1].get("voice") if history else None

    cats = list(topics)
    rng.shuffle(cats)
    cats.sort(key=lambda c: c in recent_cats)  # categories not used lately first

    plans, used_templates, used_voices, used_looks = [], set(), set(), set()
    for i in range(count):
        cat = cats[i % len(cats)]
        fresh = [t for t in topics[cat] if t not in last_used]
        if fresh:
            topic = rng.choice(fresh)
        else:  # whole category used before: reuse the least recently used topic
            topic = min(topics[cat], key=lambda t: last_used[t])

        tmpl_pool = [t for t in TEMPLATES
                     if t["name"] not in used_templates and t["name"] != last_template] or TEMPLATES
        template = rng.choice(tmpl_pool)

        voice_pool = [v for v in VOICES if v[0] not in used_voices and v[0] != last_voice] or VOICES
        voice, rate = rng.choice(voice_pool)

        look_pool = [l for l in LOOKS if l not in used_looks] or LOOKS
        look = rng.choice(look_pool)

        used_templates.add(template["name"])
        used_voices.add(voice)
        used_looks.add(look)
        last_used[topic] = len(history) + i

        plans.append({
            "category": cat,
            "topic": topic,
            "template": template["name"],
            "template_guide": template["guide"],
            "scenes": template["scenes"],
            "motion": template["motion"],
            "caption": template["caption"],
            "voice": voice,
            "rate": rate,
            "look": look,
        })
    return plans
