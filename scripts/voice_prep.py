"""配音整理与口播录音对轨：
模式一（AI 配音 / 分句音频，默认）：
  读入 项目/assets/narration.json，下载或检查 assets/voice/<id>.mp3，量每句时长，
  用 whisper 听写做中文字级对齐（核对多音字/念错、拿 [重点词] 与卡片触发时刻），按标点切分长句为 clauses，
  并计算 30fps 音量包络 env（供主讲人 IP 头像开合嘴巴），写回 narration.json 与 page/narration.js。

模式二（真人录制的整段口播，--from-recording <音频或视频>）：
  自动转为 assets/voice/recording.mp3，用 whisper 听写并分段（或按 --transcript 台本对齐每场时刻），
  默认生成连续音轨版 narration.json（fullAudio + fullEnv + origStart/origEnd + clauses），
  也可加 --slice 按句间静音切分成独立的 n1.mp3, n2.mp3... 以配合 holds 等旁白停顿。

用法：
  ~/.venvs/vocab-story/bin/python voice_prep.py 项目目录 [--no-whisper] [--model small] [--lang zh] [--max-clause 22]
  ~/.venvs/vocab-story/bin/python voice_prep.py 项目目录 --from-recording 口播.mp3 [--transcript 台本.txt] [--scenes 6] [--slice]
"""
import argparse, difflib, json, math, pathlib, re, subprocess, sys, urllib.request
import numpy as np

ENV_FPS = 30
PUNCT_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


def clean_word_chars(text: str) -> list[tuple[int, str]]:
    """提取可对齐字符及其在原文中的索引（保留中文汉字与小写字母数字）。"""
    out = []
    for idx, ch in enumerate(text):
        low = ch.lower()
        if "\u4e00" <= low <= "\u9fff" or ("a" <= low <= "z") or ("0" <= low <= "9"):
            out.append((idx, low))
    return out


def ffprobe_dur(path: pathlib.Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        text=True,
    ).strip()
    return round(float(out), 2)


def compute_env(path: pathlib.Path, fps: int = ENV_FPS) -> list[float]:
    sr = 16000
    pcm = subprocess.check_output(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(sr), "-"],
    )
    if not pcm:
        return []
    samples = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    hop = sr // fps
    n = max(1, len(samples) // hop)
    rms = np.array([float(np.sqrt(np.mean(samples[k * hop:(k + 1) * hop] ** 2))) for k in range(n)])
    active = rms[rms > 0.008]
    ref = float(np.percentile(active, 90)) if len(active) else 0.1
    v = np.clip(rms / max(ref, 1e-4), 0.0, 1.0)
    v = np.where(v < 0.12, 0.0, v)
    return [round(float(x), 2) for x in v]


def load_whisper(model_name: str, no_whisper: bool):
    if no_whisper:
        return None
    try:
        from faster_whisper import WhisperModel
        return WhisperModel(model_name, device="cpu", compute_type="int8")
    except Exception as e:
        print(f"⚠ 没法加载 whisper（{e}），跳过听写，改用字数比例估算时刻")
        return None


def transcribe_chars(model, audio: pathlib.Path, lang: str) -> tuple[list[tuple[str, float, float]], list[dict]]:
    segs_raw, _ = model.transcribe(str(audio), language=lang, word_timestamps=True)
    heard_chars: list[tuple[str, float, float]] = []
    segs: list[dict] = []
    for s in segs_raw:
        segs.append({"start": float(s.start), "end": float(s.end), "text": s.text.strip()})
        words = getattr(s, "words", None) or []
        if words:
            for w in words:
                chars = [c for _, c in clean_word_chars(w.word)]
                if not chars:
                    continue
                ws, we = float(w.start), max(float(w.start) + 0.04, float(w.end))
                k = len(chars)
                for j, ch in enumerate(chars):
                    cs = ws + (j / k) * (we - ws)
                    ce = ws + ((j + 1) / k) * (we - ws)
                    heard_chars.append((ch, cs, ce))
        else:
            chars = [c for _, c in clean_word_chars(s.text)]
            k = max(1, len(chars))
            ss, se = float(s.start), max(float(s.start) + 0.1, float(s.end))
            for j, ch in enumerate(chars):
                heard_chars.append((ch, ss + (j / k) * (se - ss), ss + ((j + 1) / k) * (se - ss)))
    return heard_chars, segs


def align_char_times(plain: str, heard_chars: list[tuple[str, float, float]], dur: float) -> tuple[dict[int, tuple[float, float]], float]:
    """把 plain 里每个非标点字符映射到录音/配音时间戳（未匹配到的字符在前后锚点间线性插值）。"""
    sc = clean_word_chars(plain)
    if not sc:
        return {}, 1.0
    if not heard_chars:
        total = max(1, len(plain))
        return {idx: (round((idx / total) * dur, 3), round(((idx + 1) / total) * dur, 3)) for idx, _ in sc}, 0.0

    s_seq = [c for _, c in sc]
    h_seq = [c for c, _, _ in heard_chars]
    sm = difflib.SequenceMatcher(None, s_seq, h_seq, autojunk=False)
    matched: dict[int, tuple[float, float]] = {}
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            _, hs, he = heard_chars[blk.b + k]
            matched[blk.a + k] = (hs, he)

    # 在首尾及相邻匹配点间插值补全未命中字符
    anchors = sorted(matched.keys())
    times_by_sc: dict[int, tuple[float, float]] = {}
    if not anchors:
        n = len(sc)
        for i, (orig_idx, _) in enumerate(sc):
            times_by_sc[orig_idx] = (dur * i / n, dur * (i + 1) / n)
    else:
        for i, (orig_idx, _) in enumerate(sc):
            if i in matched:
                times_by_sc[orig_idx] = matched[i]
                continue
            prev_a = max((a for a in anchors if a < i), default=None)
            next_a = min((a for a in anchors if a > i), default=None)
            if prev_a is None:
                t0, t1 = 0.0, matched[next_a][0]
                span = max(1, next_a)
                frac = i / span
            elif next_a is None:
                t0, t1 = matched[prev_a][1], dur
                span = max(1, len(sc) - 1 - prev_a)
                frac = (i - prev_a) / span
            else:
                t0, t1 = matched[prev_a][1], matched[next_a][0]
                span = max(1, next_a - prev_a)
                frac = (i - prev_a) / span
            t_est = t0 + max(0.0, t1 - t0) * frac
            times_by_sc[orig_idx] = (t_est, min(dur, t_est + 0.18))
    return times_by_sc, sm.ratio()


def char_time_lookup(plain: str, char_times: dict[int, tuple[float, float]], dur: float, pos: int, length: int = 1) -> tuple[float, float]:
    sub_indices = [i for i in range(pos, min(len(plain), pos + max(1, length))) if i in char_times]
    if sub_indices:
        return char_times[sub_indices[0]][0], char_times[sub_indices[-1]][1]
    frac0 = pos / max(1, len(plain))
    frac1 = min(1.0, (pos + max(1, length)) / max(1, len(plain)))
    return frac0 * dur, max(frac0 * dur + 0.15, frac1 * dur)


def split_clauses(rich_text: str, char_times: dict[int, tuple[float, float]], dur: float, max_clause: int, base_offset: float = 0.0) -> list[dict]:
    """按标点切分超长旁白为流畅短字幕，保留 [重点词] 标记。"""
    plain = re.sub(r"[\[\]]", "", rich_text).strip()
    if not plain:
        return []
    visible_len = len(re.sub(r"\s+", "", plain))
    if visible_len <= max_clause:
        return [{"text": rich_text.strip(), "offset": 0.0, "dur": round(dur, 2)}]

    # 按不破坏 [...] 的方式切分标点
    tokens: list[str] = []
    cur = []
    in_brk = False
    for ch in rich_text.strip():
        cur.append(ch)
        if ch == "[":
            in_brk = True
        elif ch == "]":
            in_brk = False
        elif not in_brk and ch in "，。！？；：、,.!?;:":
            tokens.append("".join(cur))
            cur = []
    if cur:
        tokens.append("".join(cur))

    # 合并过短片段（少于 5 字且合并后不超 max_clause + 3）
    merged: list[str] = []
    for tok in tokens:
        t_clean_len = len(re.sub(r"[\[\]\s，。！？；：、,.!?;:]", "", tok))
        if merged:
            prev_len = len(re.sub(r"[\[\]\s，。！？；：、,.!?;:]", "", merged[-1]))
            if (prev_len < 5 or t_clean_len < 5) and (prev_len + t_clean_len <= max_clause + 3):
                merged[-1] += tok
                continue
        merged.append(tok)

    # 若单段仍超 max_clause + 4，按空白再拆一次
    final_parts: list[str] = []
    for part in merged:
        p_clean_len = len(re.sub(r"[\[\]\s]", "", part))
        if p_clean_len <= max_clause + 4:
            final_parts.append(part.strip())
            continue
        # 优先按空格或顿号拆，尽量均分
        mid = len(part) // 2
        best_split = None
        for delta in range(0, len(part) // 3):
            for idx in (mid - delta, mid + delta):
                if 3 < idx < len(part) - 3 and part[idx] in " 、的在了":
                    # 确保不在 [...] 内部
                    if part[:idx].count("[") == part[:idx].count("]"):
                        best_split = idx + (0 if part[idx] == " " else 1)
                        break
            if best_split:
                break
        if best_split:
            final_parts.append(part[:best_split].strip())
            final_parts.append(part[best_split:].strip())
        else:
            final_parts.append(part.strip())

    clauses = []
    search_pos = 0
    for idx, part in enumerate(final_parts):
        part_plain = re.sub(r"[\[\]]", "", part)
        pos = plain.find(part_plain, search_pos)
        if pos < 0:
            pos = search_pos
        search_pos = pos + len(part_plain)
        ts, te = char_time_lookup(plain, char_times, dur, pos, len(part_plain))
        clauses.append({"text": part, "offset": round(max(0.0, ts - base_offset), 2), "_end": max(0.2, te - base_offset)})

    for i, c in enumerate(clauses):
        end_t = clauses[i + 1]["offset"] - 0.04 if i < len(clauses) - 1 else dur
        c["dur"] = round(max(0.35, min(dur - c["offset"], max(c["_end"] - c["offset"], end_t - c["offset"]))), 2)
        del c["_end"]
    return clauses


def extract_word_times(line: dict, plain: str, char_times: dict[int, tuple[float, float]], dur: float, base_offset: float = 0.0) -> dict[str, float]:
    targets = set(re.findall(r"\[([^\]]+)\]", line.get("zh", "")))
    for c in (line.get("cards") or ([] if not line.get("card") else [line["card"]])):
        if c.get("atWord"):
            targets.add(c["atWord"])
    words = {}
    for kw in targets:
        pos = plain.find(kw)
        if pos >= 0:
            ts, _ = char_time_lookup(plain, char_times, dur, pos, len(kw))
            words[kw] = round(max(0.0, ts - base_offset), 2)
    return words


def run_per_line(root: pathlib.Path, nar: dict, a) -> None:
    voice = root / "assets/voice"
    voice.mkdir(parents=True, exist_ok=True)
    model = load_whisper(a.model, a.no_whisper)
    nar.pop("fullAudio", None)
    nar.pop("fullEnv", None)
    nar["envFps"] = ENV_FPS

    for l in nar["lines"]:
        nid = l["id"]
        f = None
        for ext in (".mp3", ".wav", ".m4a"):
            cand = voice / f"{nid}{ext}"
            if cand.exists():
                f = cand
                break
        if f is None:
            f = voice / f"{nid}.mp3"
            if not l.get("voiceUrl"):
                sys.exit(f"缺配音 {f}，narration.json 里也没有 voiceUrl")
            req = urllib.request.Request(l["voiceUrl"], headers={"User-Agent": "Mozilla/5.0"})
            f.write_bytes(urllib.request.urlopen(req, timeout=120).read())
            print("下载", f.name)
        else:
            l["file"] = f"assets/voice/{f.name}"

        dur = ffprobe_dur(f)
        l["dur"] = dur
        l["env"] = compute_env(f, ENV_FPS)

        rich = l.get(a.lang) or l.get("zh") or l.get("en") or ""
        plain = re.sub(r"[\[\]]", "", rich)
        l.pop("words", None)
        l.pop("clauses", None)

        if model and plain:
            heard_chars, _ = transcribe_chars(model, f, a.lang)
            char_times, ratio = align_char_times(plain, heard_chars, dur)
            heard_str = "".join(c for c, _, _ in heard_chars)
            flag = "" if ratio > 0.82 else "  ⚠ 听写和原稿差别较大，请核对多音字或重配"
            print(f"{nid}  {dur:5.2f}s  原稿：{plain}\n{'':13}听写：{heard_str}{flag}")
        else:
            char_times, _ = align_char_times(plain, [], dur)

        words = extract_word_times(l, plain, char_times, dur)
        if words:
            l["words"] = words
        if rich:
            clauses = split_clauses(rich, char_times, dur, a.max_clause)
            if len(clauses) > 1:
                l["clauses"] = clauses

    write_narration(root, nar, a.lang)
    total = sum(l["dur"] for l in nar["lines"])
    print(f"共 {len(nar['lines'])} 句，配音合计 {total:.1f} 秒；已写 narration.json 和 page/narration.js")


def group_segments(segs: list[dict], target_scenes: int | None, lang="zh") -> list[dict]:
    if not segs:
        return []
    if not target_scenes or target_scenes <= 0:
        # 自动按 6~10 秒或句末标点合并成场
        groups = [dict(segs[0])]
        for s in segs[1:]:
            cur = groups[-1]
            cur_dur = cur["end"] - cur["start"]
            gap = s["start"] - cur["end"]
            if cur_dur < 5.5 and gap < 0.7 and (s["end"] - cur["start"]) <= 11.0:
                cur["end"] = s["end"]
                sep = " " if lang == "en" else "" if (cur["text"] and cur["text"][-1] in "，。！？；：") else "，"
                cur["text"] = f"{cur['text']}{sep}{s['text']}"
            else:
                groups.append(dict(s))
        return groups

    n = min(target_scenes, len(segs))
    groups = []
    for k in range(n):
        i0 = round(k * len(segs) / n)
        i1 = round((k + 1) * len(segs) / n)
        chunk = segs[i0:i1]
        text = (" " if lang == "en" else "，").join(s["text"].strip("，。") for s in chunk if s["text"].strip())
        if text and text[-1] not in "。！？":
            text += "。"
        groups.append({"start": chunk[0]["start"], "end": chunk[-1]["end"], "text": text})
    return groups


def run_from_recording(root: pathlib.Path, nar: dict, a) -> None:
    src = pathlib.Path(a.from_recording).resolve()
    if not src.is_file():
        sys.exit(f"找不到口播文件：{src}")
    voice_dir = root / "assets/voice"
    voice_dir.mkdir(parents=True, exist_ok=True)
    rec = voice_dir / "recording.mp3"
    if src != rec:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-ar", "48000", "-ac", "2", "-b:a", "192k", str(rec)], check=True)
        print(f"已规范化口播音频：{rec}")

    total_dur = ffprobe_dur(rec)
    model = load_whisper(a.model, a.no_whisper)
    heard_chars: list[tuple[str, float, float]] = []
    segs: list[dict] = []
    if model:
        heard_chars, segs = transcribe_chars(model, rec, a.lang)
        print(f"whisper 听写完成：共 {len(segs)} 个语音片段，总长 {total_dur:.2f}s")

    # 确定分场文本：优先 --transcript，其次已有 narration.json 非占位台词，再次 whisper 分段
    raw_lines: list[str] = []
    if a.transcript:
        tp = pathlib.Path(a.transcript).resolve()
        raw_lines = [ln.strip() for ln in tp.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.strip().startswith("#")]

    if raw_lines:
        full_rich = "".join(raw_lines)
        full_plain = re.sub(r"[\[\]]", "", full_rich)
        char_times, ratio = align_char_times(full_plain, heard_chars, total_dur)
        print(f"台本整轨对齐完成（匹配率 {ratio:.2f}）")
        lines = []
        cursor = 0
        for idx, rtext in enumerate(raw_lines):
            p = re.sub(r"[\[\]]", "", rtext)
            pos = full_plain.find(p, cursor)
            if pos < 0:
                pos = cursor
            cursor = pos + len(p)
            ts, te = char_time_lookup(full_plain, char_times, total_dur, pos, len(p))
            line = {"id": f"n{idx + 1}", "scene": idx + 1, a.lang: rtext, "origStart": round(ts, 2), "origEnd": round(te, 2), "dur": round(max(0.4, te - ts), 2)}
            words = extract_word_times(line, full_plain, char_times, total_dur, base_offset=ts)
            if words:
                line["words"] = words
            # 为本句局部字符偏移切分字幕
            local_ct = {k - pos: v for k, v in char_times.items() if pos <= k < pos + len(p)}
            clauses = split_clauses(rtext, local_ct, line["dur"], a.max_clause, base_offset=ts)
            if len(clauses) > 1:
                line["clauses"] = clauses
            lines.append(line)
    else:
        if not segs:
            # --no-whisper 且无台本时，退回已有 lines
            existing = nar.get("lines") or [{"id": "n1", "scene": 1, "zh": "第一段口播。"}]
            n = len(existing)
            segs = [{"start": round(total_dur * i / n, 2), "end": round(total_dur * (i + 1) / n, 2), "text": existing[i].get(a.lang, "")} for i in range(n)]
        grouped = group_segments(segs, a.scenes, a.lang)
        lines = []
        for idx, g in enumerate(grouped):
            ts, te = g["start"], g["end"]
            dur = max(0.5, te - ts)
            txt = g["text"]
            local_hc = [(c, cs - ts, ce - ts) for c, cs, ce in heard_chars if cs >= ts - 0.1 and ce <= te + 0.1]
            ct, _ = align_char_times(txt, local_hc, dur)
            line = {"id": f"n{idx + 1}", "scene": idx + 1, a.lang: txt, "origStart": round(ts, 2), "origEnd": round(te, 2), "dur": round(dur, 2)}
            clauses = split_clauses(txt, ct, dur, a.max_clause, base_offset=0.0)
            if len(clauses) > 1:
                line["clauses"] = clauses
            lines.append(line)

    if a.slice:
        nar.pop("fullAudio", None)
        nar.pop("fullEnv", None)
        nar["envFps"] = ENV_FPS
        bounds = [(l["origStart"], l["origEnd"]) for l in lines]
        for i, l in enumerate(lines):
            cur_s, cur_e = bounds[i]
            s0 = 0.0 if i == 0 else max(0.0, (bounds[i - 1][1] + cur_s) / 2)
            e0 = total_dur if i == len(lines) - 1 else min(total_dur, (cur_e + bounds[i + 1][0]) / 2)
            clip = voice_dir / f"{l['id']}.mp3"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s0:.3f}", "-to", f"{e0:.3f}", "-i", str(rec), "-b:a", "192k", str(clip)], check=True)
            shift = cur_s - s0
            l["dur"] = ffprobe_dur(clip)
            l["file"] = f"assets/voice/{clip.name}"
            l["env"] = compute_env(clip, ENV_FPS)
            if "clauses" in l:
                for c in l["clauses"]:
                    c["offset"] = round(max(0.0, c["offset"] + shift), 2)
            if "words" in l:
                l["words"] = {k: round(v + shift, 2) for k, v in l["words"].items()}
            l.pop("origStart", None)
            l.pop("origEnd", None)
        nar["lines"] = lines
        print(f"已按句切分为 {len(lines)} 段音频到 assets/voice/")
    else:
        nar["fullAudio"] = "assets/voice/recording.mp3"
        nar["audioOffset"] = 0
        nar["envFps"] = ENV_FPS
        nar["fullEnv"] = compute_env(rec, ENV_FPS)
        nar["lines"] = lines

    write_narration(root, nar, a.lang)
    scene_t = [l.get("origStart", round(sum(x["dur"] for x in lines[:i]), 2)) for i, l in enumerate(lines)]
    print(f"\n建议写入 page/story.js：")
    print(f"  duration: {math.ceil(total_dur + 1.5)},")
    print(f"  sceneT: {json.dumps(scene_t)},")


def write_narration(root: pathlib.Path, nar: dict, lang="zh") -> None:
    nar_path = root / "assets/narration.json"
    nar_path.write_text(json.dumps(nar, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    keep_keys = ("id", "en", "zh", "dur", "origStart", "origEnd", "words", "clauses", "card", "cards", "file", "env")
    js = {
        **{k: nar[k] for k in ("fullAudio", "audioOffset", "envFps", "fullEnv", "vocab") if k in nar},
        "lines": [{k: l[k] for k in keep_keys if k in l} for l in nar["lines"]],
    }
    # 引擎的子句字段是 text（中文）和 en。翻译跟随源子句的时间码。
    translations = root / "assets/subtitle_translations.json"
    bilingual = nar.get("subtitleMode") == "bilingual"
    lookup = json.loads(translations.read_text()) if bilingual and translations.exists() else {}
    for line in js["lines"]:
        clauses = line.get("clauses") or []
        rows = clauses or [line]
        source_key = "text" if clauses else lang
        translated = lookup.get(line["id"], [])
        if bilingual and len(translated) != len(rows):
            expected = [row.get(source_key, "") for row in rows]
            raise ValueError(f"{line['id']} 需按已对齐子句提供翻译：{expected}")
        output = []
        for i, row in enumerate(rows):
            row = dict(row)
            source = row.get(source_key, "")
            if lang == "en" and clauses:
                row["en"] = row.pop("text")
            if bilingual:
                pair = translated[i]
                if pair["source"] != source or not pair["translation"].strip():
                    raise ValueError(f"{line['id']} 第 {i+1} 条翻译未匹配源字幕")
                key = "en" if lang == "zh" else "text" if clauses else "zh"
                row[key] = pair["translation"]
            output.append(row)
        if clauses:
            line["clauses"] = output
        else:
            line.update(output[0])
    (root / "page").mkdir(exist_ok=True)
    (root / "page/narration.js").write_text(
        "// 由 voice_prep.py 生成，不要手改；改稿子改 assets/narration.json 后重跑\nwindow.NARRATION = "
        + json.dumps(js, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--no-whisper", action="store_true")
    ap.add_argument("--model", default="small")
    ap.add_argument("--lang", choices=["zh", "en"])
    ap.add_argument("--captions-only", action="store_true", help="复用已对齐时间，加载字幕翻译并重写页面字幕")
    ap.add_argument("--max-clause", type=int, default=20)
    ap.add_argument("--from-recording", help="单条口播音频或视频路径")
    ap.add_argument("--transcript", help="与口播对应的台本文本（每场一行）")
    ap.add_argument("--scenes", type=int, help="无台本时期望切分出的场数")
    ap.add_argument("--slice", action="store_true", help="将口播切分成每场独立音频以启用 holds 停顿")
    a = ap.parse_args()

    root = pathlib.Path(a.project).resolve()
    nar_path = root / "assets/narration.json"
    nar = json.loads(nar_path.read_text(encoding="utf-8")) if nar_path.exists() else {"lines": []}

    a.lang = a.lang or nar.get("voice", {}).get("lang", "zh")
    if a.captions_only:
        write_narration(root, nar, a.lang)
    elif a.from_recording:
        run_from_recording(root, nar, a)
    else:
        if not nar.get("lines"):
            sys.exit(f"{nar_path} 里没有 lines，请先写旁白或使用 --from-recording")
        run_per_line(root, nar, a)


if __name__ == "__main__":
    main()
