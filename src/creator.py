#!/usr/bin/env python3
"""Cloud-only AI-directed Shorts pipeline: Gemini script + Pexels footage + Gemini TTS + FFmpeg + YouTube."""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path.cwd()
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-3.8-flash-lite-tts").strip()
CHANNEL_TOPIC = os.environ.get("CHANNEL_TOPIC", "قصص قصيرة خيالية مشوقة بنهاية غير متوقعة").strip()
YOUTUBE_PRIVACY = os.environ.get("YOUTUBE_PRIVACY", "private").strip().lower()

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "CloudAIShortsFactory/1.0"})


def require_secrets() -> None:
    required = {
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "PEXELS_API_KEY": PEXELS_API_KEY,
        "YOUTUBE_CLIENT_ID": YOUTUBE_CLIENT_ID,
        "YOUTUBE_CLIENT_SECRET": YOUTUBE_CLIENT_SECRET,
        "YOUTUBE_REFRESH_TOKEN": YOUTUBE_REFRESH_TOKEN,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError("Missing required GitHub Actions secrets: " + ", ".join(missing))
    if YOUTUBE_PRIVACY not in {"private", "unlisted", "public"}:
        raise RuntimeError("YOUTUBE_PRIVACY must be private, unlisted, or public")


def request_json(method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    timeout = kwargs.pop("timeout", 90)
    response = SESSION.request(method, url, timeout=timeout, **kwargs)
    if not response.ok:
        body = response.text[:1200]
        raise RuntimeError(f"HTTP {response.status_code} from {url}: {body}")
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(f"Invalid JSON response from {url}") from exc


def generate_script() -> dict[str, Any]:
    prompt = f"""
أنت كاتب ومخرج Reels محترف. أنشئ ريلز عربي أصلي مدته 25-35 ثانية، موضوع القناة: {CHANNEL_TOPIC}.
اكتب قصة خيالية قصيرة مشوقة باللهجة المصرية الطبيعية، مع Hook قوي في أول ثانيتين ونهاية مرضية. لا تنسب القصة الخيالية إلى حادثة حقيقية، ولا تخترع حقائق على أنها حقيقية. لا تستخدم شخصيات أو مشاهد محمية من أفلام معروفة.
أخرج JSON فقط، بلا Markdown، بهذا الشكل بالضبط:
{{
  "title": "عنوان عربي جذاب لا يزيد على 65 حرفاً",
  "hook": "خطاف افتتاحي قصير على الشاشة، بحد أقصى 7 كلمات",
  "description": "وصف عربي قصير للفيديو، ثم سطر يذكر أن اللقطات المرئية من Pexels وأن النص والصوت بمساعدة الذكاء الاصطناعي",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "narration_style": "Egyptian Arabic suspenseful documentary narration, natural pacing, clear diction",
  "scenes": [
    {{"narration":"جزء صوتي باللهجة المصرية من 10 إلى 16 كلمة", "caption":"جملة بصرية قصيرة من 2 إلى 5 كلمات", "search_query":"short English search query for a suitable portrait stock video"}},
    {{"narration":"...", "caption":"...", "search_query":"..."}},
    {{"narration":"...", "caption":"...", "search_query":"..."}},
    {{"narration":"...", "caption":"...", "search_query":"..."}},
    {{"narration":"...", "caption":"...", "search_query":"..."}}
  ]
}}
الشروط:
- عدد المشاهد 5 بالضبط، وكل مشهد لقطة/فكرة مرئية مختلفة وقابلة للعثور عليها في مكتبة فيديو مجانية.
- مجموع narration بين 60 و78 كلمة عربية تقريباً. اجعل كل جملة صوتية جزءاً متتابعاً من نفس القصة ولا تكررها.
- البحث المرئي بالإنجليزية ومحدد وقابل للبحث في Pexels، مثال: "rainy empty street at night cinematic".
- captions عربية قصيرة، بلا هاشتاجات ولا علامات ترقيم كثيرة.
- العنوان والوصف والـ tags باللغة العربية. لا تذكر أن اللقطات AI-generated، لأنها لقطات مخزنة.
- اجعل المحتوى مناسباً للجمهور العام وخالياً من نصائح طبية/مالية حساسة.
""".strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    data = request_json(
        "POST", url,
        params={"key": GEMINI_API_KEY},
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.85,
            },
        },
        timeout=120,
    )
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        plan = json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Gemini did not return the expected JSON script. Try a different free model in GEMINI_MODEL.") from exc

    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != 5:
        raise RuntimeError("Gemini plan must include exactly 5 scenes")
    for i, scene in enumerate(scenes):
        for key in ("narration", "caption", "search_query"):
            if not isinstance(scene.get(key), str) or not scene[key].strip():
                raise RuntimeError(f"Gemini scene {i + 1} has no valid {key}")
        scene["narration"] = scene["narration"].strip()
        scene["caption"] = scene["caption"].strip()[:70]
        scene["search_query"] = scene["search_query"].strip()[:120]
    plan["title"] = str(plan.get("title", "قصة قصيرة مشوقة"))[:95]
    plan["hook"] = str(plan.get("hook", plan["title"]))[:80]
    plan["description"] = str(plan.get("description", "قصة قصيرة مُنتجة بمساعدة الذكاء الاصطناعي."))
    plan["tags"] = [str(t).strip().replace("#", "")[:30] for t in plan.get("tags", []) if str(t).strip()][:12]
    plan["narration"] = " ".join(scene["narration"] for scene in scenes)
    if len(plan["narration"]) < 80:
        raise RuntimeError("Generated narration is too short; refusing to create a low-quality Short")
    return plan


def generate_narration(text: str, style: str) -> Path:
    # Gemini 3.8 Flash-Lite TTS has an official free tier subject to account limits.
    url = "https://generativelanguage.googleapis.com/v1beta/interactions"
    payload = {
        "model": TTS_MODEL,
        "input": [{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": text,
                "annotations": [{
                    "type": "speech_metadata",
                    "style": "Natural Egyptian Arabic storyteller; warm, clear, suspenseful but not theatrical; medium-fast pace. " + str(style)[:160],
                }],
            }],
        }],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": "Kore"}]},
    }
    data = request_json(
        "POST", url,
        headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )
    audio_b64 = None
    if isinstance(data.get("output_audio"), dict):
        audio_b64 = data["output_audio"].get("data")
    if not audio_b64:
        for step in data.get("steps", []) if isinstance(data.get("steps"), list) else []:
            for part in step.get("content", []) if isinstance(step.get("content"), list) else []:
                if part.get("type") == "audio" and part.get("data"):
                    audio_b64 = part["data"]
    if not audio_b64:
        raise RuntimeError("Gemini TTS did not return audio data; check API access/quota/model name")
    audio_path = OUT / "narration.wav"
    audio_path.write_bytes(base64.b64decode(audio_b64))
    if audio_path.stat().st_size < 1000:
        raise RuntimeError("Gemini TTS output is unexpectedly small")
    return audio_path


def pexels_candidates(query: str) -> list[dict[str, Any]]:
    url = "https://api.pexels.com/v1/videos/search"
    data = request_json(
        "GET", url,
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "orientation": "portrait", "per_page": 8},
        timeout=60,
    )
    candidates = []
    for video in data.get("videos", []):
        files = [f for f in video.get("video_files", []) if f.get("link") and f.get("file_type", "video/mp4") == "video/mp4"]
        if not files:
            continue
        def score(file: dict[str, Any]) -> tuple[float, int]:
            w, h = int(file.get("width") or 0), int(file.get("height") or 0)
            ratio = w / h if h else 99
            return (abs(ratio - 9 / 16), w * h)
        portrait = [f for f in files if int(f.get("height") or 0) >= int(f.get("width") or 0)]
        file_list = portrait or files
        chosen = min(file_list, key=lambda f: (score(f)[0], -score(f)[1]))
        candidates.append({
            "link": chosen["link"],
            "video_page": video.get("url", "https://www.pexels.com/videos/"),
            "photographer": video.get("user", {}).get("name", "Pexels contributor"),
            "photographer_url": video.get("user", {}).get("url", "https://www.pexels.com/"),
        })
    return candidates


def download_clip(scene: dict[str, Any], index: int) -> dict[str, str]:
    queries = [scene["search_query"], "cinematic " + scene["search_query"], "abstract atmospheric cinematic b roll"]
    last_error = None
    for query in queries:
        try:
            for candidate in pexels_candidates(query):
                path = OUT / f"source_{index:02d}.mp4"
                with SESSION.get(candidate["link"], stream=True, timeout=(20, 90)) as response:
                    response.raise_for_status()
                    total = 0
                    with path.open("wb") as f:
                        for block in response.iter_content(chunk_size=1024 * 512):
                            if not block:
                                continue
                            total += len(block)
                            if total > 75 * 1024 * 1024:
                                raise RuntimeError("Pexels clip exceeded the 75 MB safety limit")
                            f.write(block)
                if path.stat().st_size < 50_000:
                    path.unlink(missing_ok=True)
                    continue
                return {"path": str(path), **candidate}
        except Exception as exc:
            last_error = exc
            (OUT / f"source_{index:02d}.mp4").unlink(missing_ok=True)
            continue
    raise RuntimeError(f"Could not find/download suitable Pexels footage for scene {index}: {last_error or 'no results'}")


def run_cmd(args: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ""


def media_duration(path: Path) -> float:
    value = run_cmd([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ], capture=True)
    try:
        duration = float(value)
    except ValueError as exc:
        raise RuntimeError(f"Could not determine media duration for {path.name}") from exc
    if duration <= 0:
        raise RuntimeError("Narration audio duration is invalid")
    return duration


def ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    centiseconds = int(round(seconds * 100))
    hours, centiseconds = divmod(centiseconds, 360000)
    minutes, centiseconds = divmod(centiseconds, 6000)
    secs, cs = divmod(centiseconds, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def ass_escape(text: str) -> str:
    return (str(text).replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N"))


def write_ass(plan: dict[str, Any], duration: float) -> Path:
    scenes = plan["scenes"]
    average = duration / len(scenes)
    content = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 720", "PlayResY: 1280", "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Caption,Noto Naskh Arabic,43,&H00FFFFFF,&H0000FFFF,&H00101010,&HB0000000,-1,0,0,0,100,100,0,0,3,2,1,2,46,46,150,1",
        "Style: Hook,Noto Naskh Arabic,58,&H0000D7FF,&H0000D7FF,&H00101010,&HAA000000,-1,0,0,0,100,100,0,0,3,3,1,8,42,42,120,1",
        "Style: SceneTag,Noto Naskh Arabic,40,&H00FFFFFF,&H0000FFFF,&H00101010,&HAA000000,-1,0,0,0,100,100,0,0,3,2,1,8,42,42,230,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    hook_end = min(3.2, duration)
    content.append(f"Dialogue: 2,{ass_time(0)},{ass_time(hook_end)},Hook,,0,0,0,,{ass_escape(plan['hook'])}")
    cursor = 0.0
    for scene in scenes:
        # Give every narration chunk a proportional subtitle slot; voice cadence can still vary slightly.
        chunk_duration = max(0.1, average)
        start = cursor
        end = min(duration, start + chunk_duration + 0.08)
        content.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Caption,,0,0,0,,{ass_escape(scene['narration'])}")
        tag_start = start + (0.15 if start > 0 else 0.45)
        tag_end = min(end, tag_start + min(2.3, max(0.7, chunk_duration - 0.2)))
        if scene.get("caption") and tag_end > tag_start:
            content.append(f"Dialogue: 0,{ass_time(tag_start)},{ass_time(tag_end)},SceneTag,,0,0,0,,{ass_escape(scene['caption'])}")
        cursor += chunk_duration
    path = OUT / "captions.ass"
    path.write_text("\n".join(content), encoding="utf-8-sig")
    return path


def create_video(plan: dict[str, Any], clips: list[dict[str, str]], narration_path: Path) -> Path:
    voice_duration = media_duration(narration_path)
    transition_duration = 0.35
    # Overlaps between scenes reduce the total stitched duration; account for them here.
    segment_duration = max(3.8, (voice_duration + transition_duration * (len(clips) - 1)) / len(clips))
    normalized = []
    for i, clip in enumerate(clips, 1):
        target = OUT / f"normalized_{i:02d}.mp4"
        run_cmd([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-stream_loop", "-1", "-i", clip["path"], "-t", f"{segment_duration:.3f}",
            "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30,eq=contrast=1.04:saturation=1.08",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30", str(target)
        ])
        normalized.append(target)

    silent_video = OUT / "silent_concat.mp4"
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for clip_path in normalized:
        command.extend(["-i", str(clip_path)])
    filters = []
    for i in range(len(normalized)):
        filters.append(f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS,fps=30,format=yuv420p[v{i}]")
    previous = "v0"
    for i in range(1, len(normalized)):
        result_label = f"xf{i}"
        offset = i * (segment_duration - transition_duration)
        filters.append(
            f"[{previous}][v{i}]xfade=transition=fade:duration={transition_duration:.3f}:offset={offset:.3f}[{result_label}]"
        )
        previous = result_label
    command.extend([
        "-filter_complex", ";".join(filters), "-map", f"[{previous}]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-an", str(silent_video)
    ])
    run_cmd(command)
    caption_file = write_ass(plan, voice_duration)
    final = OUT / "youtube_short.mp4"
    # Paths have no colons on GitHub-hosted Linux runners, so the filter argument is safe as written.
    run_cmd([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(silent_video), "-i", str(narration_path),
        "-vf", f"subtitles={caption_file.as_posix()}",
        "-map", "0:v:0", "-map", "1:a:0", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(final)
    ])
    if not final.exists() or final.stat().st_size < 300_000:
        raise RuntimeError("Final video is missing or unexpectedly small")
    return final


def upload_to_youtube(video_path: Path, plan: dict[str, Any], clips: list[dict[str, str]]) -> str:
    creds = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    attribution_lines = ["\nVisual footage via Pexels:"]
    seen = set()
    for clip in clips:
        line = f"- Video by {clip['photographer']}: {clip['video_page']}"
        if line not in seen:
            attribution_lines.append(line)
            seen.add(line)
    attribution_lines.append("Pexels: https://www.pexels.com/\n")
    description = (plan["description"].strip() + "\n\n" + " ".join(attribution_lines))[:4900]
    tags = [re.sub(r"[^\w\u0600-\u06FF ]", "", t).strip()[:30] for t in plan.get("tags", [])]
    tags = [t for t in tags if t][:15]
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": plan["title"][:100],
                "description": description,
                "tags": tags,
                "categoryId": "24",
                "defaultLanguage": "ar",
                "defaultAudioLanguage": "ar",
            },
            "status": {
                "privacyStatus": YOUTUBE_PRIVACY,
                "selfDeclaredMadeForKids": False,
            },
        },
        media_body=MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True),
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"YouTube upload progress: {int(status.progress() * 100)}%")
    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("YouTube API did not return a video ID")
    return f"https://www.youtube.com/watch?v={video_id}"


def main() -> None:
    require_secrets()
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule":
        print("Scheduled cloud run started")
    print("Step 1/5: generating an original Arabic story and shot list with Gemini...")
    plan = generate_script()
    (OUT / "story_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Step 2/5: generating Arabic narration with Gemini TTS...")
    audio_path = generate_narration(plan["narration"], plan.get("narration_style", ""))

    print("Step 3/5: finding and downloading licensed stock footage from Pexels...")
    clips = []
    for i, scene in enumerate(plan["scenes"], 1):
        print(f"Finding clip {i}/{len(plan['scenes'])}...")
        clips.append(download_clip(scene, i))
        time.sleep(0.25)

    print("Step 4/5: rendering vertical video and burning in Arabic captions...")
    video_path = create_video(plan, clips, audio_path)
    metadata = {
        "title": plan["title"], "youtube_privacy": YOUTUBE_PRIVACY,
        "scenes": [{"search_query": x["search_query"], "caption": x["caption"], "narration": x["narration"]} for x in plan["scenes"]],
        "sources": [{"url": x["video_page"], "photographer": x["photographer"], "photographer_url": x["photographer_url"]} for x in clips],
        "note": "Visual footage consists of Pexels stock clips selected by an AI-generated shot list; the actual footage is not generated from scratch by a video model."
    }
    (OUT / "video_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Step 5/5: uploading to YouTube...")
    url = upload_to_youtube(video_path, plan, clips)
    (OUT / "youtube_url.txt").write_text(url + "\n", encoding="utf-8")
    print("SUCCESS: YouTube upload completed with privacy='" + YOUTUBE_PRIVACY + "'.")
    print("Video URL: " + url)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("WORKFLOW FAILED: " + str(exc), file=sys.stderr)
        sys.exit(1)
