"""YouTube Data API v3: upload a Short and (optionally) approve it later."""
import os

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube"]


def _service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri=TOKEN_URI,
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(video_path, script, cfg, privacy="private", publish_at=None):
    """Upload a video. `publish_at` (RFC3339 UTC) only works with privacy='private'. Returns the video id."""
    from googleapiclient.http import MediaFileUpload

    ycfg = cfg["youtube"]
    tags = list(dict.fromkeys(ycfg.get("default_tags", []) + script.get("hashtags", [])))
    hashtags = " ".join(f"#{t.replace(' ', '')}" for t in script.get("hashtags", [])[:5])
    description = f"{script['description']}\n\n{hashtags} #Shorts"

    status = {
        "privacyStatus": privacy,
        "selfDeclaredMadeForKids": ycfg.get("made_for_kids", False),
        "containsSyntheticMedia": ycfg.get("synthetic_media", True),
    }
    if publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at

    body = {
        "snippet": {
            "title": script["title"],
            "description": description,
            "tags": tags[:20],
            "categoryId": ycfg.get("category_id", "26"),
        },
        "status": status,
    }
    yt = _service()
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=-1)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]


def make_public(video_id, cfg):
    ycfg = cfg["youtube"]
    yt = _service()
    yt.videos().update(part="status", body={
        "id": video_id,
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": ycfg.get("made_for_kids", False),
            "containsSyntheticMedia": ycfg.get("synthetic_media", True),
        },
    }).execute()
