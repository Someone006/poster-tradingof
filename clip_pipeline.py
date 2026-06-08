import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / ".tools" / "python"
WORK = ROOT / "clip-work"
SOURCES = WORK / "sources"
CLIPS = ROOT / "clips"
STATE_PATH = WORK / "processed.json"
MANIFEST_PATH = CLIPS / "manifest.json"
CHANNEL_URL = "https://www.youtube.com/@AndreaCimi/videos"
FFMPEG_EXE = TOOLS / "imageio_ffmpeg" / "binaries" / "ffmpeg-win-x86_64-v7.1.exe"


def run(command, check=True):
    print("+ " + " ".join(str(part) for part in command), flush=True)
    completed = subprocess.run(command, cwd=ROOT, text=True)
    if check and completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed


def python_exe():
    return Path(sys.executable)


def ensure_paths():
    for path in (WORK, SOURCES, CLIPS):
        path.mkdir(parents=True, exist_ok=True)


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_ffmpeg():
    if FFMPEG_EXE.exists():
        return FFMPEG_EXE
    sys.path.insert(0, str(TOOLS))
    import imageio_ffmpeg

    return Path(imageio_ffmpeg.get_ffmpeg_exe())


def ytdlp_args(*args):
    command = [str(python_exe()), str(TOOLS / "yt_dlp" / "__main__.py"), "--paths", str(SOURCES)]
    if FFMPEG_EXE.exists():
        command.extend(["--ffmpeg-location", str(FFMPEG_EXE)])
    command.extend(args)
    return command


def list_channel(limit):
    command = ytdlp_args("--flat-playlist", "--dump-json", "--playlist-end", str(limit), CHANNEL_URL)
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr)
        raise SystemExit(result.returncode)
    videos = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        video_id = item.get("id")
        if video_id:
            videos.append(
                {
                    "id": video_id,
                    "title": item.get("title") or video_id,
                    "url": item.get("url") if str(item.get("url", "")).startswith("http") else f"https://www.youtube.com/watch?v={video_id}",
                }
            )
    return videos


def download_video(video):
    output = SOURCES / f"{video['id']}.%(ext)s"
    run(
        ytdlp_args(
            "-f",
            "bv*[height<=1080]+ba/b[height<=1080]/best[height<=1080]/best",
            "--merge-output-format",
            "mp4",
            "--write-info-json",
            "--no-overwrites",
            "-o",
            str(output),
            video["url"],
        )
    )
    matches = sorted(SOURCES.glob(f"{video['id']}.*"))
    media = [path for path in matches if path.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
    merged = SOURCES / f"{video['id']}.mp4"
    if merged.exists():
        return merged
    if not media:
        raise RuntimeError(f"No media file downloaded for {video['id']}")
    video_media = [path for path in media if ".f" not in path.stem]
    return video_media[0] if video_media else media[0]


def probe_duration(ffmpeg, media):
    ffprobe = ffmpeg.with_name("ffprobe.exe")
    if not ffprobe.exists():
        ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 90.0
    result = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 90.0


def make_clip(ffmpeg, video, media, index, start, duration):
    safe_id = video["id"]
    clip_name = f"{safe_id}_clip_{index:02d}.mp4"
    out = CLIPS / clip_name
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    run(
        [
            str(ffmpeg),
            "-y",
            "-ss",
            f"{start:.2f}",
            "-t",
            f"{duration:.2f}",
            "-i",
            str(media),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(out),
        ]
    )
    title = f"{video['title']} | Clip {index}"
    caption = f"{video['title']}\n\n#shorts #reels #tiktok #tradingof #viral"
    (CLIPS / f"{safe_id}_clip_{index:02d}.txt").write_text(
        f"Title: {title}\n\nCaption:\n{caption}\n\nSource: {video['url']}\nStart: {start:.2f}s\nDuration: {duration:.2f}s\n",
        encoding="utf-8",
    )
    return {
        "file": str(out.relative_to(ROOT)),
        "metadata_file": str((CLIPS / f"{safe_id}_clip_{index:02d}.txt").relative_to(ROOT)),
        "video_id": safe_id,
        "source_url": video["url"],
        "source_title": video["title"],
        "clip_index": index,
        "start_seconds": round(start, 2),
        "duration_seconds": round(duration, 2),
        "title": title,
        "caption": caption,
    }


def process(limit, clips_per_video):
    ensure_paths()
    ffmpeg = get_ffmpeg()
    state = load_json(STATE_PATH, {"processed_videos": {}})
    manifest = load_json(MANIFEST_PATH, {"clips": []})
    videos = list_channel(limit)
    created = []
    for video in videos:
        if video["id"] in state["processed_videos"]:
            continue
        media = download_video(video)
        duration = probe_duration(ffmpeg, media)
        if duration < 60:
            state["processed_videos"][video["id"]] = {"skipped": True, "reason": "Video shorter than 60 seconds"}
            save_json(STATE_PATH, state)
            continue
        clip_duration = min(90.0, max(60.0, duration))
        usable = max(0.0, duration - clip_duration)
        count = max(1, clips_per_video)
        video_clips = []
        for index in range(1, count + 1):
            start = 0.0 if count == 1 else usable * ((index - 1) / max(1, count - 1))
            item = make_clip(ffmpeg, video, media, index, start, clip_duration)
            manifest["clips"].append(item)
            created.append(item)
            video_clips.append(item)
        state["processed_videos"][video["id"]] = {"clips": len(video_clips), "title": video["title"], "url": video["url"]}
        save_json(STATE_PATH, state)
        save_json(MANIFEST_PATH, manifest)
    print(json.dumps({"created": created, "manifest": str(MANIFEST_PATH)}, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--clips-per-video", type=int, default=1)
    args = parser.parse_args()
    process(args.limit, args.clips_per_video)


if __name__ == "__main__":
    main()
