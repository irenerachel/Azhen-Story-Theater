# 故事小剧场

给一个人物、一段故事或一段口播录音，生成带旁白和字幕的分层动画。可以做全屏故事，也可以给主讲人留出画中画位置。交付文件为 MP4 和 SRT。

**《拉瓦锡与一瓶空气》成片截图**

![复古绘本风格的实验室场景](preview/lavoisier.jpg)

## 安装到 Codex 或 Claude Code

下列命令适用于已安装 Homebrew 的 macOS，在 zsh 终端中运行。选择 Codex 时使用下面的目录，选择 Claude Code 时把第一行改成 `SKILLS="$HOME/.claude/skills"`。两个工作室可共用 Python 环境和音效库。

```zsh
SKILLS="$HOME/.codex/skills"
export SK="$SKILLS/azhen-story-theater"
mkdir -p "$SKILLS"
git clone https://github.com/irenerachel/Azhen-Story-Theater.git "$SK"
```

已有 Git 克隆的用户可在该目录执行 `git pull --ff-only` 更新。也可从 GitHub 的 **Code → Download ZIP** 下载，解压后将包含 `SKILL.md` 的整个目录放到上面的 `$SK` 位置。安装后开启新会话，用中文描述任务即可。

```text
用故事小剧场做一条 60 秒横版动画，讲苏轼夜游赤壁。先给我看分镜和人物设定，我来录旁白。
```

## 获取渲染器和音效

仓库的 `renderer/` 已包含逐帧渲染器、抽帧预览工具、成片检查脚本和音效下载清单。上面的克隆和 ZIP 都包含这些文件。首次运行需要联网安装软件、浏览器和音效。

```zsh
brew install ffmpeg node uv
export PY="$HOME/.venvs/vocab-story/bin/python"
[[ -x "$PY" ]] || uv venv --python 3.11 "$HOME/.venvs/vocab-story"
uv pip install --python "$PY" faster-whisper numpy pillow scipy scikit-image fonttools brotli

export CTV="$SK/renderer"
"$PY" "$CTV/scripts/sound_library.py" fetch
"$PY" "$CTV/scripts/sound_library.py" verify
zsh "$SK/scripts/doctor.sh"
```

音效默认存入 `~/Documents/Codex/素材库/code-to-video-sounds`。如要换盘，在运行上述音效命令前设置 `export CTV_SOUND_LIB="/你的音效库目录"`。下载中断可以重跑 `fetch`，然后用 `verify` 检查。音效来源见 `renderer/assets/SOUND-LICENSES.md`。Whisper small 模型会在首次使用语音对齐时下载。

已有完整 `code-to-video-studio` 的用户可以将 `CTV` 设为它的绝对路径。未设置时，脚本依次查找 Codex 的 skills 目录、Claude 的 skills 目录、当前仓库的 `renderer/`。运行 `zsh "$SK/scripts/renderer_path.sh"` 可查看实际路径。手动渲染时，在同一个终端保留 `SK`、`PY`、`CTV` 三个变量。

## 从项目到成片

1. 在终端创建工程。脚本会安装项目自己的 npm 依赖和 Playwright Chromium。`P` 可改为自己的项目目录，最后一个参数可选 `16:9` 或 `9:16`。

```zsh
export P="$HOME/Documents/story-theater-demo"
zsh "$SK/scripts/new_project.sh" "$P" 16:9
cd "$P"
export PLAYWRIGHT_MODULE="$P/node_modules/playwright"
```

2. 把工程目录交给 Agent，按 `SKILL.md` 完成脚本、插画、配音和时间轴。故事样例位于 `assets/example-story/`。先确认分镜与人物设定，再准备背景、透明角色和口播。可用自带生图工具或自备插画，配音可用系统朗读、真人录音或已配置的 LibTV。 初始化生成的是工程骨架，下面的导出步骤用于素材已就绪的工程。

3. 在工程目录抽帧预览，检查字幕、人物位置和遮挡，然后导出旁白时间轴。

```zsh
node "$CTV/scripts/preview.mjs" page 8
node "$SK/scripts/export_timeline.mjs" .
```

4. 做逐镜审核。先运行下面的预检，查看 `build/stage-audit/` 中的画面和动作预览，再按 `references/blocking.md` 将实际观察与当前 digest 写入 `build/stage-audit/review.json`。修改过素材或走位后需重新预检。

```zsh
node "$SK/scripts/stage-audit.mjs" "$P"
```

5. 通过审核后导出并混音。渲染脚本会在开始和结束时核对审核记录。

```zsh
zsh "$SK/scripts/render_checked.sh" "$P" "$P/build/v1"
"$PY" "$SK/scripts/mix_voice.py" . build/v1/output/page.mp4 build/v1/mix-page.wav "成片/story.mp4"
"$PY" "$CTV/scripts/check_video.py" "成片/story.mp4" --sheet "成片/contact-sheet.png"
```

最终视频和字幕分别是 `成片/story.mp4` 与 `成片/story.srt`。遇到浏览器缺失，在工程目录运行 `npx playwright install chromium`；遇到音效缺失，检查 `CTV_SOUND_LIB` 并重新运行音效校验。
