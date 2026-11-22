#!/bin/zsh
# 开工前检查环境。每一项不就绪时会打印安装命令。
ok() { print "✓ $1" }; bad() { print "✗ $1"; FAIL=1 }
which ffmpeg >/dev/null && which ffprobe >/dev/null && ok "ffmpeg / ffprobe" || bad "ffmpeg（brew install ffmpeg）"
which node >/dev/null && ok "node $(node -v)" || bad "node（brew install node）"
PY=~/.venvs/vocab-story/bin/python
if [[ -x $PY ]] && $PY -c "import numpy, PIL, scipy, skimage" 2>/dev/null; then
  ok "Python 环境 ~/.venvs/vocab-story"
else
  bad "Python 环境：uv venv -p 3.11 ~/.venvs/vocab-story && uv pip install -p ~/.venvs/vocab-story/bin/python faster-whisper numpy pillow scipy scikit-image"
fi
[[ -x $PY ]] && $PY -c "import faster_whisper" 2>/dev/null && ok "whisper（字幕分句 / 录音对轨）" || print "· 没有 faster-whisper：AI 配音可估算，但录音自动切句不可用"
ls ~/.cache/huggingface/hub 2>/dev/null | grep -q faster-whisper-small && ok "whisper small 模型已缓存" || print "· whisper small 模型第一次运行时会自动下载（约 460 MB）"
CTV=${CTV:-}
[[ -n $CTV ]] || { [[ -f ~/.codex/skills/code-to-video-studio/scripts/render_page.mjs ]] && CTV=~/.codex/skills/code-to-video-studio || CTV=~/.claude/skills/code-to-video-studio; }
[[ -f $CTV/scripts/render_page.mjs ]] && ok "code-to-video-studio 渲染器 ($CTV)" || bad "找不到 code-to-video-studio skill（渲染器 render_page.mjs 在里面）"
LIB=${CTV_SOUND_LIB:-~/Documents/Codex/素材库/code-to-video-sounds}
[[ -f $LIB/catalog.json ]] && ok "音效库" || bad "音效库不在 $LIB（python3 $CTV/scripts/sound_library.py fetch）"
ls -d ~/Library/Caches/ms-playwright/chromium-*(N) >/dev/null 2>&1 && ok "playwright 浏览器 $(ls -d ~/Library/Caches/ms-playwright/chromium-*(N) | xargs -n1 basename | tr '\n' ' ')" || print "· 还没有 playwright 浏览器，new_project.sh 会自动下载"
if command -v libtv >/dev/null 2>&1 || [[ -x ~/.libtv/libtv ]]; then
  ok "libtv CLI（AI 生图 / 配音 / BGM）"
else
  print "· 未检测到 libtv CLI：可用本地自备插图与口播录音，或先安装 libtv"
fi
exit ${FAIL:-0}
