#!/bin/zsh
set -eu
sk=${0:A:h:h}
p=${1:A}
out=${2:A}
initial=$(node "$sk/scripts/stage-audit.mjs" "$p" --check)
ctv=${CTV:-$HOME/.codex/skills/code-to-video-studio}
[[ -f "$ctv/scripts/render_page.mjs" ]] || ctv="$HOME/.claude/skills/code-to-video-studio"
PLAYWRIGHT_MODULE="$p/node_modules/playwright" node "$ctv/scripts/render_page.mjs" "$p/page" --out "$out"
final=$(node "$sk/scripts/stage-audit.mjs" "$p" --check)
[[ "$final" == "$initial" ]] || { print -u2 "渲染中素材发生变化，请重新渲染"; exit 1; }
print "$final" > "$out/output/page.stage-digest"
shasum -a 256 "$out/output/page.mp4" | cut -d ' ' -f1 >> "$out/output/page.stage-digest"
