"""Writes one unique reel script per plan using the Claude API (or a canned script in --dry-run)."""
import json
import os
import re

SYSTEM = """You write short vertical-video scripts for a health and beauty channel with an AI presenter.
Rules:
- General wellness and beauty-habit advice only. NEVER claim to cure, treat, prevent or diagnose any condition. No promises of results. No 'doctors hate this' style claims.
- Friendly, natural spoken English. Short sentences. No jargon.
- Each reel must feel different: follow the structure guide you are given and use a fresh hook.
- Total narration 85-115 words (about 35-45 seconds when spoken).
Return ONLY valid JSON, no markdown fences."""

USER_TMPL = """Write a reel script.

Topic: {topic}
Category: {category}
Structure to follow ({template}): {guide}
Number of scenes: {scenes}
Visual setting for the presenter: {look}

Return JSON with exactly these keys:
{{
  "title": "catchy title under 70 characters, no clickbait, no hashtags",
  "description": "2-3 sentence description for YouTube. End with: 'General wellness information only, not medical advice. AI-generated presenter.'",
  "hashtags": ["5 to 7 relevant hashtags without the # symbol"],
  "scenes": [
    {{"narration": "what the presenter says in this scene (1-2 short sentences)",
      "image_prompt": "describe the presenter in this scene: pose, action, props, setting. Photorealistic, vertical, no text in the image."}}
  ]
}}
The scenes array must contain exactly {scenes} items."""


def _parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start:end + 1])


def _validate(script, plan):
    for key in ("title", "description", "hashtags", "scenes"):
        if key not in script:
            raise ValueError(f"Script missing '{key}'")
    scenes = script["scenes"]
    if not isinstance(scenes, list) or len(scenes) < 3:
        raise ValueError("Script has too few scenes")
    for s in scenes:
        if not s.get("narration") or not s.get("image_prompt"):
            raise ValueError("A scene is missing narration or image_prompt")
    words = sum(len(s["narration"].split()) for s in scenes)
    if words > 150:
        raise ValueError(f"Script too long ({words} words)")
    script["title"] = script["title"][:95]
    return script


def _call_anthropic(prompt, cfg):
    import anthropic  # imported lazily so other providers work without the package/key

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=cfg["llm"]["model"],
        max_tokens=cfg["llm"]["max_tokens"],
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _call_gemini(prompt, cfg):
    """Google Gemini REST API (has a free tier with daily limits; check current limits on ai.google.dev)."""
    import time
    import requests

    key = os.environ["GEMINI_API_KEY"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['llm']['model']}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": max(cfg["llm"].get("max_tokens", 1800), 4096),  # room for 'thinking' tokens
            "temperature": 1.0,
        },
    }
    for attempt in range(4):
        r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=120)
        if r.status_code in (429, 500, 503):  # rate limit / busy: wait and retry
            time.sleep(15 * (attempt + 1))
            continue
        r.raise_for_status()
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    raise RuntimeError("Gemini is busy or the free quota is used up for now")


PROVIDERS = {"anthropic": _call_anthropic, "gemini": _call_gemini}


def generate(plan, cfg, dry_run=False):
    if dry_run:
        return _canned(plan)
    provider = cfg["llm"].get("provider", "anthropic")
    call = PROVIDERS[provider]
    prompt = USER_TMPL.format(
        topic=plan["topic"], category=plan["category"], template=plan["template"],
        guide=plan["template_guide"], scenes=plan["scenes"], look=plan["look"],
    )
    last_err = None
    for _ in range(3):
        text = call(prompt, cfg)
        try:
            return _validate(_parse_json(text), plan)
        except Exception as e:  # retry with a fresh generation
            last_err = e
    raise RuntimeError(f"Could not get a valid script: {last_err}")


def _canned(plan):
    n = plan["scenes"]
    scenes = [{
        "narration": f"Dry run scene {i + 1} about {plan['topic']}.",
        "image_prompt": f"presenter, scene {i + 1}, {plan['look']}",
    } for i in range(n)]
    return {
        "title": f"[dry run] {plan['topic']}"[:95],
        "description": "Dry run. General wellness information only, not medical advice. AI-generated presenter.",
        "hashtags": ["health", "beauty", "wellness"],
        "scenes": scenes,
    }
