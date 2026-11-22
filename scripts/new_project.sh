#!/bin/zsh
# 新建一个故事视频项目：目录、动画引擎、字体、依赖一次放好。
# 用法：new_project.sh 项目目录 [16:9|9:16]
set -e
SK=${0:A:h:h}; P=${1:?用法：new_project.sh 项目目录 [16:9|9:16]}; ASP=${2:-16:9}
[[ $ASP == 16:9 || $ASP == 9:16 ]] || { print "画幅只支持 16:9 或 9:16"; exit 1 }
mkdir -p "$P"/{page,lib,build,成片} "$P"/assets/{raw,bg,cut,voice,host,fonts}
cp "$SK"/assets/engine/{engine.js,demo.js,fx.js,blocking.js} "$P/lib/"
cp "$SK/assets/engine/index.html" "$P/page/index.html"
[[ -f "$P/page/story.js" ]] || sed "s/^const ASPECT = \"16:9\";/const ASPECT = \"$ASP\";/" "$SK/assets/engine/story-skeleton.js" > "$P/page/story.js"
print "$ASP" > "$P/page/aspect.txt"
cp -R "$SK/assets/fonts/ChillRoundGothic" "$P/assets/fonts/"
[[ -f "$P/assets/urls.txt" ]] || print "# 每行：名字 网址。B 开头是背景，C 开头是角色/道具图，H 开头是主讲人头像\n" > "$P/assets/urls.txt"
if [[ ! -f "$P/assets/narration.json" ]]; then
  cat > "$P/assets/narration.json" <<'JSON'
{
  "voice": {
    "mode": "design",
    "model": "Seed Audio 1.0",
    "gender": "female",
    "speed": 1.08
  },
  "lines": [
    {
      "id": "n1",
      "scene": 1,
      "zh": "写第一句旁白，用 [方括号] 标出重点词。"
    },
    {
      "id": "n2",
      "scene": 2,
      "zh": "写第二句旁白。"
    }
  ]
}
JSON
fi
# 新项目保留可执行的两镜头示例；实际故事逐镜替换标定。
if [[ ! -f "$P/page/blocking.json" ]]; then
  python3 - "$P/page/blocking.json" "$ASP" <<'PYBLOCK'
import json,sys
from pathlib import Path
w,h=(1920,1080) if sys.argv[2]=="16:9" else (1080,1920)
shots={}
for name,horizon,unit in [("scene1",.42,.34),("scene2",.43,.32)]:
    shots[name]={"ground":[h*horizon,h*unit,h*(.75 if name=="scene1" else .73)],"surface":[.67*h,.82*h],
                 "action":"原位换姿势","camera":{"intent":"围绕前景人物推近","zoom":[1,1.12]}}
shots['scene1']['limbChecks']=[{'name':'换姿','start':3.08,'end':3.32,'crop':[round(w*.25),round(h*.16),round(w*.65),round(h*.65)]}]
Path(sys.argv[1]).write_text(json.dumps({"width":w,"height":h,"sizes":{"C01":.98,"C02":1.04,"C05":.85,"C08":1},"shots":shots},ensure_ascii=False,indent=2))
PYBLOCK
fi
cd "$P"
[[ -f package.json ]] || print '{"name":"story-video-project","private":true}' > package.json
PWV=""
for d in ~/Library/Caches/ms-playwright/chromium-*(N); do
  case ${d:t} in chromium-1134) PWV="@1.47.2";; chromium-1140) PWV="@1.48.2";; esac
done
npm i gsap@3.13.0 playwright${PWV} @fontsource/fraunces >/dev/null 2>&1
if ! node -e 'const fs=require("fs"),pw=require("playwright");process.exit(fs.existsSync(pw.chromium.executablePath())?0:1)' 2>/dev/null; then
  npx playwright install chromium
fi
print "项目已建好：$P（画幅 $ASP）"
print "下一步：确认提纲后写好 assets/narration.json（或跑 voice_prep.py --from-recording 导入录音）"
