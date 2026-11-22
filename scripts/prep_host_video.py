"""预处理主讲人出镜口播视频（真人或数字人视频）：
1) 统一转为 30fps CFR H.264 到 项目/assets/host/video.mp4；
2) 抽取封面首帧到 项目/assets/host/poster.jpg（供动画预览阶段占位展示）；
3) 加上 --extract-voice 时，抽取出干净音频到 项目/assets/voice/recording.mp3，可直接喂给 voice_prep.py --from-recording。
用法：~/.venvs/vocab-story/bin/python prep_host_video.py <口播视频路径> <项目目录> [--extract-voice] [--fps 30]"""
import argparse, pathlib, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("project")
ap.add_argument("--extract-voice", action="store_true")
ap.add_argument("--fps", type=int, default=30)
a = ap.parse_args()

src = pathlib.Path(a.video).resolve()
if not src.is_file():
    sys.exit(f"找不到视频文件：{src}")
root = pathlib.Path(a.project).resolve()
host_dir = root / "assets/host"
voice_dir = root / "assets/voice"
host_dir.mkdir(parents=True, exist_ok=True)
voice_dir.mkdir(parents=True, exist_ok=True)

out_vid = host_dir / "video.mp4"
out_poster = host_dir / "poster.jpg"

subprocess.run([
    "ffmpeg", "-v", "error", "-y", "-i", str(src),
    "-vf", f"fps={a.fps},format=yuv420p",
    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
    str(out_vid),
], check=True)

subprocess.run([
    "ffmpeg", "-v", "error", "-y", "-ss", "0.2", "-i", str(out_vid),
    "-frames:v", "1", "-q:v", "2", str(out_poster),
], check=True)
print(f"✓ 主讲人视频已规范化：{out_vid}")
print(f"✓ 封面帧已生成：{out_poster}")

if a.extract_voice:
    out_mp3 = voice_dir / "recording.mp3"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(src),
        "-vn", "-ar", "48000", "-ac", "2", "-b:a", "192k", str(out_mp3),
    ], check=True)
    print(f"✓ 口播音频已提取：{out_mp3}")
    print(f"下一步：~/.venvs/vocab-story/bin/python voice_prep.py {root} --from-recording {out_mp3}")
