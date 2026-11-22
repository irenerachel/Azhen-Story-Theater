"""用 macOS 已安装的声音，按项目台本生成分场旁白。"""
import argparse
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--voice", required=True, help="say -v '?' 所列的对应语种声音")
    args = parser.parse_args()
    assets = args.project.resolve() / "assets"
    nar = json.loads((assets / "narration.json").read_text())
    lang = nar.get("voice", {}).get("lang", "zh")
    dest = assets / "voice"
    dest.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=dest) as tmp:
        for line in nar["lines"]:
            text = line.get("tts") or line[lang]
            source = Path(tmp) / "speech.aiff"
            encoded = Path(tmp) / "speech.mp3"
            subprocess.run(["say", "-v", args.voice, "-o", str(source), "-f", "-"],
                           input=re.sub(r"[\[\]]", "", text), text=True, check=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(source),
                            "-b:a", "160k", str(encoded)], check=True)
            encoded.replace(dest / (line["id"] + ".mp3"))


if __name__ == "__main__":
    main()
