"""把配音按时间轴混进渲染器输出的音效/音乐混音，支持自定义 BGM 与可选真人/数字人口播视频画中画叠加，
两遍 loudnorm 到 -14 LUFS 封装成片，并同时导出 SRT 字幕（与成片同名）。

用法：
  python3 mix_voice.py 项目目录 <渲染出的 mp4> <渲染出的 mix-page.wav> <输出 mp4>
      [--bgm assets/bgm.mp3] [--bgm-db -24]
      [--host-video assets/host/video.mp4] [--host-pos right|left] [--host-shape circle|rounded|cutout] [--host-green]
"""
import argparse, json, pathlib, subprocess, sys
from PIL import Image, ImageDraw


def make_host_overlays(build_dir: pathlib.Path, size: int, shape: str) -> tuple[pathlib.Path, pathlib.Path]:
    """用 4 倍超采样生成抗锯齿圆角/圆形遮罩与双色边框，比 FFmpeg geq 快且边缘平滑。"""
    S4 = size * 4
    mask4 = Image.new("L", (S4, S4), 0)
    dm = ImageDraw.Draw(mask4)
    ring4 = Image.new("RGBA", (S4, S4), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ring4)

    pad = 16
    if shape == "rounded":
        rad = round(size * 0.16) * 4
        dm.rounded_rectangle([pad, pad, S4 - pad, S4 - pad], radius=rad, fill=255)
        dr.rounded_rectangle([pad - 8, pad - 8, S4 - pad + 8, S4 - pad + 8], radius=rad + 8, outline=(255, 255, 255, 255), width=12)
        dr.rounded_rectangle([pad, pad, S4 - pad, S4 - pad], radius=rad, outline=(43, 35, 32, 255), width=20)
    else:
        dm.ellipse([pad, pad, S4 - pad, S4 - pad], fill=255)
        dr.ellipse([pad - 8, pad - 8, S4 - pad + 8, S4 - pad + 8], outline=(255, 255, 255, 255), width=12)
        dr.ellipse([pad, pad, S4 - pad, S4 - pad], outline=(43, 35, 32, 255), width=20)

    mask_p = build_dir / "host_mask.png"
    ring_p = build_dir / "host_ring.png"
    mask4.resize((size, size), Image.LANCZOS).save(mask_p)
    ring4.resize((size, size), Image.LANCZOS).save(ring_p)
    return mask_p, ring_p


def ts(x: float) -> str:
    ms = round(x * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("video")
    ap.add_argument("mix")
    ap.add_argument("out")
    ap.add_argument("--bgm", help="自定义背景音乐（传入时自动优先复用 sfx-stem 避开内置曲目）")
    ap.add_argument("--bgm-db", type=float, default=-24.0)
    ap.add_argument("--host-video", help="主讲人出镜口播视频")
    ap.add_argument("--host-pos", choices=["left", "right"])
    ap.add_argument("--host-shape", choices=["circle", "rounded", "cutout"])
    ap.add_argument("--host-green", action="store_true", help="对主讲人视频启用绿幕抠像")
    a = ap.parse_args()

    root = pathlib.Path(a.project).resolve()
    audit = pathlib.Path(__file__).with_name("stage-audit.mjs")
    digest = subprocess.check_output(["node", str(audit), str(root), "--check"], text=True).strip()
    seal = pathlib.Path(a.video).with_suffix(".stage-digest")
    import hashlib
    with pathlib.Path(a.video).open("rb") as video_stream:
        sha = hashlib.sha256()
        for chunk in iter(lambda: video_stream.read(1024*1024), b""):
            sha.update(chunk)
    if not seal.is_file() or seal.read_text().splitlines() != [digest, sha.hexdigest()]:
        sys.exit("画面尚未通过当前版本的镜头校正，请先运行 render_checked.sh。")
    tl = json.loads((root / "build/voice-timeline.json").read_text(encoding="utf-8"))
    dur = float(tl["duration"])

    # 若指定了自定义 --bgm，优先找同目录的 sfx-stem-xxx.wav 以免叠了两首音乐
    base_mix = pathlib.Path(a.mix).resolve()
    if a.bgm:
        stem_name = base_mix.name.replace("mix-", "sfx-stem-", 1)
        stem_path = base_mix.with_name(stem_name)
        if stem_path.exists():
            base_mix = stem_path

    # ---------- 1. 混音（音效 + 配音 + 可选自定义 BGM） ----------
    args = ["ffmpeg", "-v", "error", "-y", "-i", str(base_mix)]
    voices = tl.get("voice") or []
    for v in voices:
        args += ["-i", str(root / v["file"])]
    bgm_idx = None
    if a.bgm:
        bgm_path = pathlib.Path(a.bgm)
        if not bgm_path.is_absolute():
            bgm_path = root / bgm_path
        if not bgm_path.is_file():
            sys.exit(f"找不到 BGM 文件：{bgm_path}")
        bgm_idx = 1 + len(voices)
        args += ["-stream_loop", "-1", "-i", str(bgm_path)]

    parts = []
    n = len(voices)
    for i, v in enumerate(voices, 1):
        delay_ms = max(0, round(float(v["start"]) * 1000))
        parts.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,volume=2.5dB,adelay={delay_ms}:all=1[v{i}]")

    mix_labels = ["[0:a]"]
    if n == 1:
        mix_labels.append("[v1]")
    elif n > 1:
        parts.append("".join(f"[v{i}]" for i in range(1, n + 1)) + f"amix=inputs={n}:normalize=0:dropout_transition=0[vo]")
        mix_labels.append("[vo]")

    if bgm_idx is not None:
        fo_st = max(0.0, dur - 1.5)
        parts.append(
            f"[{bgm_idx}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
            f"volume={a.bgm_db}dB,afade=t=in:d=0.4,afade=t=out:st={fo_st:.3f}:d=1.5[bgm]"
        )
        mix_labels.append("[bgm]")

    parts.append(f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:normalize=0:dropout_transition=0,atrim=0:{dur:.3f}[out]")
    pre = root / "build/mix-voice-pre.wav"
    subprocess.run(args + ["-filter_complex", ";".join(parts), "-map", "[out]", str(pre)], check=True)

    m = subprocess.run(
        ["ffmpeg", "-i", str(pre), "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr
    j = json.loads(m[m.rindex("{"):m.rindex("}") + 1])
    fin = root / "build/mix-voice.wav"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(pre),
        "-af",
        f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
        f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:linear=true,aresample=48000",
        str(fin),
    ], check=True)

    # ---------- 2. 封装成片（可选叠加真人/数字人出镜视频） ----------
    out_path = pathlib.Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if a.host_video:
        hv = pathlib.Path(a.host_video)
        if not hv.is_absolute():
            hv = root / hv
        if not hv.is_file():
            sys.exit(f"找不到主讲人视频：{hv}")
        hlayout = tl.get("host") or {}
        asp = (root / "page/aspect.txt").read_text().strip() if (root / "page/aspect.txt").exists() else "16:9"
        tall = asp == "9:16"
        size = int(hlayout.get("size") or (200 if tall else 220))
        pos = a.host_pos or hlayout.get("pos") or "right"
        shape = a.host_shape or hlayout.get("shape") or "circle"
        W, H = (1080, 1920) if tall else (1920, 1080)
        mx = 72 if tall else 76
        bot = 205 if tall else 72
        hx = int(hlayout["x"]) if "x" in hlayout else (W - mx - size if pos == "right" else mx)
        hy = int(hlayout["y"]) if "y" in hlayout else (H - bot - size)

        if shape == "cutout" or a.host_green:
            hbox = int(hlayout.get("height") or round(size * 1.25))
            hy_cut = int(hlayout["y"]) if "y" in hlayout else (H - bot - hbox)
            fc = (
                f"[1:v]scale=w={size}:h={hbox}:force_original_aspect_ratio=decrease,format=rgba,"
                f"chromakey=0x00FF00:0.18:0.08,despill=green[hv];"
                f"[0:v][hv]overlay=x={hx}+({size}-overlay_w)/2:y={hy_cut}+({hbox}-overlay_h):eof_action=pass:shortest=0,format=yuv420p[v]"
            )
            subprocess.run([
                "ffmpeg", "-v", "error", "-y", "-i", a.video, "-i", str(hv), "-i", str(fin),
                "-filter_complex", fc, "-map", "[v]", "-map", "2:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_path),
            ], check=True)
        else:
            mask_p, ring_p = make_host_overlays(root / "build", size, shape)
            fc = (
                f"[1:v]scale=w={size}:h={size}:force_original_aspect_ratio=increase,crop={size}:{size},format=rgba[hs];"
                f"[2:v]format=gray[hm];[hs][hm]alphamerge[hcirc];"
                f"[0:v][hcirc]overlay=x={hx}:y={hy}:eof_action=pass:shortest=0[v1];"
                f"[v1][3:v]overlay=x={hx}:y={hy}:format=auto,format=yuv420p[v]"
            )
            subprocess.run([
                "ffmpeg", "-v", "error", "-y", "-i", a.video, "-i", str(hv), "-i", str(mask_p), "-i", str(ring_p), "-i", str(fin),
                "-filter_complex", fc, "-map", "[v]", "-map", "4:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_path),
            ], check=True)
    else:
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-i", a.video, "-i", str(fin),
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out_path),
        ], check=True)

    # ---------- 3. 导出 SRT 字幕 ----------
    srt_blocks = []
    for i, s in enumerate(tl.get("subs") or [], 1):
        txt = s.get("zh") or s.get("en") or ""
        if s.get("zh") and s.get("en"):
            txt = f"{s['zh']}\n{s['en']}"
        srt_blocks.append(f"{i}\n{ts(float(s['start']))} --> {ts(float(s['end']))}\n{txt}\n")
    out_path.with_suffix(".srt").write_text("\n".join(srt_blocks), encoding="utf-8")
    print("完成", str(out_path))


if __name__ == "__main__":
    main()
