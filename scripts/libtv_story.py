"""故事小剧场专用 LibTV CLI 封装（调用本机 `libtv` 命令完成建画布、传设定图、生背景/动作/主讲人、AI配音与纯音乐 BGM）。

用法（在项目根目录执行，或加 --project 项目目录）：
  python3 libtv_story.py init "<片名>"
  python3 libtv_story.py sheet "<角色设定表提示词>" [16:9]
  python3 libtv_story.py upload-sheet <本地设定图路径>
  python3 libtv_story.py bg <B1> "<背景空镜提示词>" [16:9|9:16]
  python3 libtv_story.py pose <C01> "<角色动作提示词>" [3:4|1:1|16:9]
  python3 libtv_story.py host <H_avatar> "<主讲人头像提示词>" [1:1|3:4]
  python3 libtv_story.py vo-design
  python3 libtv_story.py vo [n1 n2 ...]
  python3 libtv_story.py bgm "<纯音乐描述>" [assets/bgm.mp3]

常用环境变量：
  VOICE_MODE          默认读 narration.json voice.mode，未设时为 design（Seed Audio 1.0 Voice-Design + audio2audio）；传 preset 用固定音色
  VOICE_MODEL         design 模式默认 Seed Audio 1.0；preset 模式默认 Minimax-speech-2.8-hd
  VOICE_GENDER        默认读 narration.json voice.gender，未设时为 female（可选 female / male）
  VOICE_REF_NODE      默认 ai-voice-ref
  VOICE_DESIGN_PROMPT 覆盖默认音色设计提示词
  VOICE_REF_FILE      可选：本地音色参考音频路径（直接上传复用）
  SPEED               默认读 narration.json voice.speed，未设时为 1.08
  BGM_MODEL           默认 Mureka V8（可选 ElevenMusic V3 / Seed Audio 1.0）
  IMG_MODEL           默认 Lib Image 2.5 Pro
  IMG_RES             默认 2K
"""
from array import array
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time

LIBTV = shutil.which("libtv") or str(Path.home() / ".libtv" / "libtv")
LOG_LOCK = threading.Lock()


def resolve_root_and_args(argv: list[str]) -> tuple[Path, list[str]]:
    if len(argv) >= 2 and argv[0] == "--project":
        return Path(argv[1]).resolve(), argv[2:]
    return Path.cwd().resolve(), argv


ROOT, ARGS = resolve_root_and_args(sys.argv[1:])
LOG_DIR = ROOT / "build" / "libtv_log"


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with LOG_LOCK, (LOG_DIR / "run.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_libtv(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [LIBTV, *args]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    entry = {"cmd": cmd[1:], "rc": res.returncode, "out": res.stdout[-4000:], "err": res.stderr[-4000:]}
    with LOG_LOCK, (LOG_DIR / "calls.log").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    if check and res.returncode != 0:
        detail = res.stderr.strip()[-600:] or res.stdout.strip()[-600:]
        raise RuntimeError(f"libtv {' '.join(args[:3])} 失败：{detail}")
    return res


def parse_last_json(text: str):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if ln.startswith("{"):
            try:
                return json.loads(ln)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def project_uuid() -> str | None:
    state = ROOT / ".libtv" / "project.json"
    if not state.exists():
        return None
    data = json.loads(state.read_text(encoding="utf-8"))
    return data.get("projectUuid") or data.get("uuid") or (data.get("projectMeta") or {}).get("uuid")


def node_exists(name: str) -> bool:
    return run_libtv("node", name, check=False).returncode == 0


def ensure_project(name: str = "故事小剧场") -> str:
    uuid = project_uuid()
    if not uuid:
        res = run_libtv("project", "create", name)
        data = parse_last_json(res.stdout) or {}
        uuid = data.get("uuid") or data.get("projectUuid") or (data.get("projectMeta") or {}).get("uuid")
        if not uuid:
            raise RuntimeError("创建画布未返回 projectUuid，请查看 build/libtv_log/calls.log")
        run_libtv("project", "use", uuid)
        log(f"画布已创建并绑定：{name} -> https://www.liblib.tv/canvas?projectId={uuid}")
    return uuid


def run_node(name: str, kind: str, prompt: str, sets: dict, lefts: list[str] | tuple[str, ...] = ()) -> dict:
    args = ["--prompt", prompt]
    for left in lefts:
        args.extend(["--left", left])
    for k, v in sets.items():
        args.extend(["-s", f"{k}={v}"])
    cmd = ["node", name, *args, "--run"] if node_exists(name) else ["node", "create", name, "-t", kind, *args, "--run"]
    res = run_libtv(*cmd)
    (LOG_DIR / f"{name}.jsonl").write_text(res.stdout, encoding="utf-8")
    data = parse_last_json(res.stdout) or {}
    if data.get("status") not in (None, 2):
        raise RuntimeError(f"节点 {name} 未完成：{data}")
    return data


def download_node(name: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    for wm in ("false", "true"):
        with tempfile.TemporaryDirectory(dir=LOG_DIR) as tmp:
            res = run_libtv("download", "-n", name, "--watermark", wm, "-o", tmp, check=False)
            files = [Path(ln.strip()) for ln in res.stdout.splitlines() if ln.strip()]
            if res.returncode == 0 and files and files[0].is_file():
                shutil.copyfile(files[0], dest)
                return dest
    info = parse_last_json(run_libtv("node", name).stdout) or {}
    urls = (info.get("data") or {}).get("url") or []
    if not urls:
        raise RuntimeError(f"节点 {name} 没有可下载的 URL，请查看 build/libtv_log/calls.log")
    subprocess.run(["curl", "-fsSL", "--retry", "2", urls[0], "-o", str(dest)], check=True)
    return dest


def f0_median(path: Path) -> tuple[float, float]:
    sr = 16000
    pcm = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
        capture_output=True, check=True,
    ).stdout
    if not pcm:
        return 0.0, 0.0
    win, hop = 640, 320
    min_lag, max_lag = sr // 380, sr // 70
    f0s: list[float] = []
    try:
        import numpy as np
        samples = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
        dur = len(samples) / sr
        for start in range(0, max(0, len(samples) - win + 1), hop):
            frame = samples[start:start + win]
            x = frame - frame.mean()
            if float(np.sqrt(np.mean(x * x))) < 0.015:
                continue
            corrs = []
            for lag in range(min_lag, max_lag + 1):
                a, b = x[:-lag], x[lag:]
                denom = float(np.sqrt(np.dot(a, a) * np.dot(b, b)))
                corrs.append(float(np.dot(a, b)) / denom if denom > 1e-9 else 0.0)
            max_r = max(corrs)
            if max_r < 0.45:
                continue
            best_idx = corrs.index(max_r)
            thresh = max(0.45, 0.85 * max_r)
            for idx in range(1, len(corrs) - 1):
                if corrs[idx] >= thresh and corrs[idx] >= corrs[idx - 1] and corrs[idx] >= corrs[idx + 1]:
                    best_idx = idx
                    break
            f0s.append(sr / (min_lag + best_idx))
    except ImportError:
        raw = array("h")
        raw.frombytes(pcm)
        dur = len(raw) / sr
        samples_py = [v / 32768.0 for v in raw]
        for start in range(0, max(0, len(samples_py) - win + 1), hop):
            frame = samples_py[start:start + win]
            mean = sum(frame) / win
            x = [v - mean for v in frame]
            if math.sqrt(sum(v * v for v in x) / win) < 0.015:
                continue
            corrs = []
            for lag in range(min_lag, max_lag + 1):
                n = win - lag
                e1 = sum(x[i] * x[i] for i in range(n))
                e2 = sum(x[i + lag] * x[i + lag] for i in range(n))
                denom = math.sqrt(e1 * e2)
                corrs.append(sum(x[i] * x[i + lag] for i in range(n)) / denom if denom > 1e-9 else 0.0)
            max_r = max(corrs)
            if max_r < 0.45:
                continue
            best_idx = corrs.index(max_r)
            thresh = max(0.45, 0.85 * max_r)
            for idx in range(1, len(corrs) - 1):
                if corrs[idx] >= thresh and corrs[idx] >= corrs[idx - 1] and corrs[idx] >= corrs[idx + 1]:
                    best_idx = idx
                    break
            f0s.append(sr / (min_lag + best_idx))
    return (round(statistics.median(f0s), 1) if f0s else 0.0), round(dur, 2)


def load_voice_cfg() -> dict:
    nar_path = ROOT / "assets" / "narration.json"
    if nar_path.is_file():
        return json.loads(nar_path.read_text(encoding="utf-8")).get("voice", {})
    return {}


def f0_ok(gender: str, f0: float, is_ref: bool = False) -> bool:
    if gender == "male":
        lo, hi = (75.0, 188.0) if is_ref else (70.0, 195.0)
        return lo <= f0 <= hi
    return f0 >= (200.0 if is_ref else 190.0)


DEFAULT_FEMALE_PROMPT = (
    "二十八岁左右的中国女性人物故事讲述者，标准普通话，声线清亮温润，自然松弛，"
    "咬字干净，略带叙事画面感，像给朋友讲一个精彩的人物传奇，语速适中。"
    "请以同一个年轻女性干声试读：那年冬天，他在一条不到两米宽的巷子里支起了第一张桌子，谁也没想到故事会从这里开始。"
)
DEFAULT_MALE_PROMPT = (
    "三十岁左右的中国男性人物故事讲述者，标准普通话，声线沉稳清朗、有故事感，"
    "吐字清晰自然，不刻意端着播音腔，像面对面给朋友讲一段鲜为人知的经历。"
    "请以同一个成年男性干声试读：那年冬天，他在一条不到两米宽的巷子里支起了第一张桌子，谁也没想到故事会从这里开始。"
)


def ensure_designed_voice(ref_node: str | None = None) -> str:
    vcfg = load_voice_cfg()
    gender = os.environ.get("VOICE_GENDER", vcfg.get("gender", "female")).lower()
    lang = vcfg.get("lang", "zh")
    ref_node = ref_node or os.environ.get("VOICE_REF_NODE", f"ai-{gender}-voice-ref" + ("-en" if lang == "en" else ""))
    ref_cache = ROOT / "assets" / "voice" / f"{ref_node}.wav"

    if node_exists(ref_node):
        if not ref_cache.is_file():
            download_node(ref_node, ref_cache)
        f0, dur = f0_median(ref_cache)
        if dur >= 2.0 and f0_ok(gender, f0, is_ref=True):
            log(f"✓ 复用画布 AI 音色参考 {ref_node}（F0={f0}Hz, {dur}s）")
            return ref_node
        log(f"· 已有参考 {ref_node} 音色不符（F0={f0}Hz, {dur}s），重生成")
        run_libtv("node", "delete", ref_node, check=False)
        ref_cache.unlink(missing_ok=True)

    ref_file = os.environ.get("VOICE_REF_FILE") or vcfg.get("refFile")
    if ref_file and Path(ref_file).is_file():
        run_libtv("upload", ref_node, "-t", "audio", "-f", ref_file)
        ref_cache.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ref_file, ref_cache)
        log(f"✓ 已上传本地音色参考：{ref_file}")
        return ref_node

    base_prompt = os.environ.get("VOICE_DESIGN_PROMPT") or vcfg.get("designPrompt") or (
        f"自然清晰的成年{gender}英语故事旁白。用英语试读：One winter morning, a traveler stepped ashore." if lang == "en" else DEFAULT_MALE_PROMPT if gender == "male" else DEFAULT_FEMALE_PROMPT
    )
    suffixes = (
        ["", "（强调：必须为沉稳清朗的成年男性嗓音，禁止女声或尖细童声）", "（强调：纯男性干声试读，中低音区自然稳重）"]
        if gender == "male"
        else ["", "（强调：必须是清亮年轻成年女性声线，禁止男声或低沉嗓音）", "（强调：标准女声讲述者，纯女声干声试读）"]
    )
    sets = {
        "model": os.environ.get("VOICE_MODEL", vcfg.get("model", "Seed Audio 1.0")),
        "scene": "Voice-Design",
        "modeType": "text2audio",
        "language": lang,
        "format": "wav",
        "sampleRate": 24000,
        "expression": os.environ.get("VOICE_EXPRESSION", vcfg.get("expression", "自然")),
    }
    for attempt, extra in enumerate(suffixes, 1):
        try:
            run_libtv("node", "delete", ref_node, check=False)
            run_node(ref_node, "audio", base_prompt + extra, sets)
            download_node(ref_node, ref_cache)
            f0, dur = f0_median(ref_cache)
            if dur >= 2.0 and f0_ok(gender, f0, is_ref=True):
                log(f"✓ AI 音色设计成功 {ref_node}（第 {attempt} 次，F0={f0}Hz, {dur}s）")
                return ref_node
            log(f"· AI 音色第 {attempt} 次不合基频区间：F0={f0}Hz, dur={dur}s")
        except Exception as err:
            log(f"· AI 音色第 {attempt} 次失败：{err}")
        run_libtv("node", "delete", ref_node, check=False)
        time.sleep(3)
    raise RuntimeError(f"AI 音色设计 {ref_node} 三次均未通过（gender={gender}）")


def check_generated_alpha(dest):
    # 使用技能已有的 Pillow 环境，CLI 主进程可继续使用系统 Python。
    py = Path.home() / ".venvs/vocab-story/bin/python"
    subprocess.run([str(py) if py.exists() else sys.executable, "-c",
                    "from PIL import Image; from native_alpha import check_alpha; "
                    "import sys; im=Image.open(sys.argv[1]); check_alpha(im, sys.argv[1])",
                    str(dest)], cwd=Path(__file__).resolve().parent, check=True)


def cmd_sheet(prompt: str, ratio: str = "16:9") -> None:
    ensure_project()
    sets = {
        "model": os.environ.get("IMG_MODEL", "Lib Image 2.5 Pro"),
        "modeType": "text2image",
        "ratio": ratio,
        "count": 1,
        "background": "transparent",
        "resolution": os.environ.get("IMG_RES", "2K"),
    }
    dest = ROOT / "assets" / "raw" / "char_sheet.png"
    run_node("char-sheet", "image", prompt, sets)
    download_node("char-sheet", dest)
    check_generated_alpha(dest)
    log(f"✓ 角色设定表已生成：{dest}")


def cmd_upload_sheet(path: str) -> None:
    ensure_project()
    src = Path(path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"找不到设定图：{src}")
    run_libtv("node", "delete", "char-sheet", check=False)
    run_libtv("upload", "char-sheet", "-t", "image", "-f", str(src))
    dest = ROOT / "assets" / "raw" / "char_sheet.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src != dest:
        shutil.copyfile(src, dest)
    log(f"✓ 已上传角色设定表到画布节点 char-sheet")


def cmd_bg(key: str, prompt: str, ratio: str | None = None) -> None:
    ensure_project()
    if not ratio:
        asp_file = ROOT / "page" / "aspect.txt"
        ratio = asp_file.read_text().strip() if asp_file.exists() else "16:9"
    sets = {
        "model": os.environ.get("IMG_MODEL", "Lib Image 2.5 Pro"),
        "modeType": "text2image",
        "ratio": ratio,
        "count": 1,
        "background": "opaque",
        "resolution": os.environ.get("IMG_RES", "2K"),
    }
    dest = ROOT / "assets" / "raw" / f"{key}.png"
    run_node(f"bg-{key}", "image", prompt, sets)
    download_node(f"bg-{key}", dest)
    log(f"✓ 背景空镜已生成：{dest}")


def cmd_pose(key: str, prompt: str, ratio: str = "3:4") -> None:
    ensure_project()
    use_sheet = node_exists("char-sheet")
    if not use_sheet and (ROOT / "assets" / "raw" / "char_sheet.png").is_file():
        cmd_upload_sheet(str(ROOT / "assets" / "raw" / "char_sheet.png"))
        use_sheet = True
    full_prompt = prompt
    if use_sheet and "{{Image 1}}" not in full_prompt and "{{Node" not in full_prompt:
        full_prompt = f"参考{{{{Image 1}}}}里的对应角色，保持长相、发型、服装和画风完全一致。{full_prompt}"
    sets = {
        "model": os.environ.get("IMG_MODEL", "Lib Image 2.5 Pro"),
        "modeType": "image2image" if use_sheet else "text2image",
        "ratio": ratio,
        "count": 1,
        "background": "transparent",
        "resolution": os.environ.get("IMG_RES", "2K"),
    }
    dest = ROOT / "assets" / "raw" / f"{key}.png"
    run_node(f"pose-{key}", "image", full_prompt, sets, lefts=["char-sheet"] if use_sheet else ())
    download_node(f"pose-{key}", dest)
    check_generated_alpha(dest)
    log(f"✓ 角色/道具图已生成：{dest}")


def cmd_host(key: str, prompt: str, ratio: str = "1:1") -> None:
    ensure_project()
    sets = {
        "model": os.environ.get("IMG_MODEL", "Lib Image 2.5 Pro"),
        "modeType": "text2image",
        "ratio": ratio,
        "count": 1,
        "background": "transparent",
        "resolution": os.environ.get("IMG_RES", "2K"),
    }
    dest = ROOT / "assets" / "raw" / f"{key}.png"
    run_node(f"host-{key}", "image", prompt, sets)
    download_node(f"host-{key}", dest)
    check_generated_alpha(dest)
    log(f"✓ 主讲人头像已生成：{dest}")


def cmd_vo(keys: list[str]) -> None:
    ensure_project()
    nar = json.loads((ROOT / "assets" / "narration.json").read_text(encoding="utf-8"))
    vcfg = nar.get("voice", {})
    lang = vcfg.get("lang", "zh")
    mode = os.environ.get("VOICE_MODE", vcfg.get("mode", "design")).lower()
    gender = os.environ.get("VOICE_GENDER", vcfg.get("gender", "female")).lower()
    speed = str(os.environ.get("SPEED", vcfg.get("speed", "1.08")))
    only = set(keys)
    todo = [line for line in nar["lines"] if not only or line["id"] in only]
    if not todo:
        raise SystemExit(f"narration.json 里找不到指定的句子：{keys}")

    if mode != "preset":
        ref_node = ensure_designed_voice()
        role_hint = "男性" if gender == "male" else "女性"
        sets = {
            "model": os.environ.get("VOICE_MODEL", vcfg.get("model", "Seed Audio 1.0")),
            "modeType": "audio2audio",
            "language": lang,
            "format": "mp3",
            "sampleRate": 24000,
            "speed": speed,
            "expression": os.environ.get("VOICE_EXPRESSION", vcfg.get("expression", "自然")),
        }

        def one_design(line: dict) -> None:
            nid = line["id"]
            node = f"vo-{nid}"
            raw_text = line.get("tts") or re.sub(r"[\[\]]", "", line.get(lang) or line.get("zh") or line.get("en", ""))
            prompt = f"沿用参考音频中同一位成年{role_hint}的音色，以{'英语' if lang == 'en' else '标准普通话'}自然讲述，只朗读以下台词，一人干声：{raw_text}"
            dest = ROOT / "assets" / "voice" / f"{nid}.mp3"
            for attempt in range(3):
                try:
                    if attempt > 0:
                        run_libtv("node", "delete", node, check=False)
                    run_node(node, "audio", prompt, sets, lefts=[ref_node])
                    download_node(node, dest)
                    f0, dur = f0_median(dest)
                    if dur < 0.4 or not f0_ok(gender, f0, is_ref=False):
                        raise RuntimeError(f"基频或时长异常（F0={f0}Hz, dur={dur}s）")
                    log(f"✓ 配音 {dest.name}（F0={f0}Hz, {dur}s）")
                    return
                except Exception as err:
                    log(f"· 配音 {node} 第 {attempt + 1} 次失败：{err}")
                    time.sleep(4)
            raise RuntimeError(f"配音 {node} 三次均失败")

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(one_design, todo))
        return

    model = os.environ.get("VOICE_MODEL", "Minimax-speech-2.8-hd")
    if lang == "en" and not (vcfg.get("voiceId") or os.environ.get("VOICE_ID")):
        raise SystemExit("英文预设音色需指定 LibTV 可用的英文 voiceId，或使用默认设计音色。")
    voice_id = os.environ.get("VOICE_ID", vcfg.get("voiceId", "Chinese (Mandarin)_Warm_Bestie"))
    voice_card = json.dumps({
        "voiceId": voice_id,
        "name": vcfg.get("voiceName", "故事旁白"),
        "gender": "Male" if gender == "male" else "Female",
        "language": vcfg.get("language", "English" if lang == "en" else "中文(普通话)"),
    }, ensure_ascii=False)
    sets = {"model": model, "scene": "Text-to-Speech", "voiceCard": voice_card, "speed": speed}

    def one_preset(line: dict) -> None:
        nid = line["id"]
        node = f"vo-pre-{nid}"
        raw_text = line.get("tts") or re.sub(r"[\[\]]", "", line.get(lang) or line.get("zh") or line.get("en", ""))
        dest = ROOT / "assets" / "voice" / f"{nid}.mp3"
        for attempt in range(3):
            try:
                run_node(node, "audio", raw_text, sets)
                download_node(node, dest)
                log(f"✓ 配音 {dest.name}")
                return
            except Exception as err:
                log(f"· 配音 {node} 第 {attempt + 1} 次失败：{err}")
                time.sleep(4)
        raise RuntimeError(f"配音 {node} 三次均失败")

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(one_preset, todo))


def cmd_bgm(prompt: str, out_arg: str | None = None) -> None:
    ensure_project()
    model = os.environ.get("BGM_MODEL", "Mureka V8")
    node = os.environ.get("BGM_NODE", "bgm-main")
    dest = ROOT / (out_arg or "assets/bgm.mp3")
    if "seed" in model.lower():
        sets = {"model": model, "force_instrumental": 1}
    elif "eleven" in model.lower() or "智能音乐" in model:
        sets = {"model": model, "scene": "Music", "duration": os.environ.get("BGM_MS", "120000"), "instrumental": 1}
    else:
        sets = {"model": model, "scene": "Music", "instrumental": 1}
    run_node(node, "audio", prompt, sets)
    download_node(node, dest)
    log(f"✓ 背景音乐 {dest}")


def main() -> None:
    if not ARGS or ARGS[0] in ("-h", "--help"):
        print(__doc__.strip())
        return
    if not Path(LIBTV).exists() and not shutil.which("libtv"):
        sys.exit("找不到 libtv 命令，请先安装并执行 libtv login")
    sub, rest = ARGS[0], ARGS[1:]
    if sub == "init":
        ensure_project(rest[0] if rest else "故事小剧场")
    elif sub == "sheet":
        cmd_sheet(rest[0], rest[1] if len(rest) > 1 else "16:9")
    elif sub == "upload-sheet":
        cmd_upload_sheet(rest[0])
    elif sub == "bg":
        cmd_bg(rest[0], rest[1], rest[2] if len(rest) > 2 else None)
    elif sub == "pose":
        cmd_pose(rest[0], rest[1], rest[2] if len(rest) > 2 else "3:4")
    elif sub == "host":
        cmd_host(rest[0], rest[1], rest[2] if len(rest) > 2 else "1:1")
    elif sub == "vo-design":
        ensure_project()
        ensure_designed_voice(rest[0] if rest else None)
    elif sub == "vo":
        cmd_vo(rest)
    elif sub == "bgm":
        cmd_bgm(rest[0], rest[1] if len(rest) > 1 else None)
    else:
        sys.exit(f"未知子命令：{sub}\n\n" + __doc__.strip())


if __name__ == "__main__":
    main()
