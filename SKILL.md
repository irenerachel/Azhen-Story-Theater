---
name: azhen-story-theater
description: 故事小剧场视频工作室：用户给一个人物故事主题、大纲、文字稿，或自己录好的口播音频/出镜视频，后台用代码动态图形 + 一致性角色插图（默认调用系统自带生图工具，若系统无支持原生透明 PNG 的生图工具则先询问用户是否使用 LibTV）搓出 1～2 分钟的故事小剧场动画视频（默认横版 16:9，也支持竖版 9:16）。支持 LibTV AI 配音、系统朗读及真人录音对齐，默认埃尔热欧洲清线漫画，每个镜头保留独立人物与完整无人背景、两种画面模式（全屏纯故事小剧场，或预留主讲人出镜位——2D IP 说话头像 / 真人口播画中画），可选四种旁白与字幕组合、独立生词贴、重点词高亮、可选人物/年份信息卡、多种转场与主线物件光圈片尾。用户说“讲个关于 xxx 的故事视频”“我录了口播你在背后帮我配故事动画”“做一个人物传奇小剧场”“按故事动画流程出一条视频”时使用。做纯科普图表、干货条漫时用 azhen-mg-video；做英语背单词动画 + 测验网页时用 azhen-vocab-story-studio。
---

# 故事小剧场视频工作室（Story Video Studio）

把一个人物、一段历史或一个奇闻故事，变成 **2.5D 纸片偶小剧场动画视频** + **SRT 字幕文件**。
你只要在开头确认**故事分镜台本**与**角色设定表**，后面的透明素材生成、配音/对轨、写动画、抽帧自检和渲染合成全部在后台自动完成。

## 这个 Skill 里有什么

| 位置 | 内容 |
|---|---|
| `assets/engine/` | 通用动画引擎 `engine.js`（不改）、页面外壳 `index.html`、`demo.js`、`fx.js`、故事骨架 `story-skeleton.js` |
| `assets/example-story/` | 完整人物故事示例（`narration.json`、`story.js`、`brief.md`） |
| `assets/fonts/ChillRoundGothic/` | 寒蝉圆黑体 Medium / Bold（SIL OFL 1.1，可商用） |
| `scripts/libtv_story.py` | 封装 `libtv` CLI：AI 设计女声/男声配音、纯音乐 BGM；以及在系统没有生图工具或无法生成原生透明 PNG 并经用户明确同意后的生图（建画布、生设定表/空镜/原生透明角色） |
| `scripts/voice_prep.py` | 配音与口播对轨：量时长、whisper 中文字级对齐、长句自动分句、生成 30fps 口型包络 `env`；支持 `--from-recording` 直接吃真人录音 |
| `scripts/prep_host_video.py` | 主讲人出镜视频预处理：统一 30fps、抽封面帧、提取口播音频 |
| `scripts/fetch_assets.py` | 整理 `assets/raw/` 或 `urls.txt`：背景裁切、角色原生 Alpha 校验与裁边、主讲人头像整理 |
| `scripts/contact_sheet.py` / `split_sprite.py` | 带 5% 刻度的抠图联系表（量身高系数 `fact`、查手持道具）、双人拆分 |
| `scripts/export_timeline.mjs` / `mix_voice.py` | 导出时间轴并做重叠检查；混音（配音 + 音效 + 可选 BGM，-14 LUFS）、可选叠加真人视频画中画、输出 MP4 + SRT |
| `references/production-notes.md` | 写 `story.js` 的引擎接口、安全区坐标（含主讲人槽位）、版式审查红线与清理指南。**写动画前读** |
| `references/prompts.md` | 7 套人物故事画风模板、生图工具优先级与回退规则、出图提示词、内容过滤改法。**出图前读** |

安装步骤与依赖见仓库根目录的 README.md。Python 脚本使用 `PY=~/.venvs/vocab-story/bin/python`。以下命令中的 `$CTV` 是渲染器目录，可运行 `zsh <本 skill>/scripts/renderer_path.sh` 查询。仓库自带渲染、抽帧、成片检查工具和音效下载清单。

---

## 流程

### 0. 开工选择

运行 `zsh <本 skill>/scripts/doctor.sh` 检查环境（`ffmpeg`、`node`、`faster-whisper`、`$CTV` 渲染器、音效库、`libtv`）。

新项目第一次回复列出下表中尚未确定的语言选项，并提供生词贴开关。主题、画风和语音来源一并收齐。用户已指定的选项直接采用。用户说“按默认”即可采用默认项。已有项目的局部修改沿用已定选择。

| 语言预设 | 旁白 | 字幕 |
|---|---|---|
| 纯中文（默认） | 中文 | 中文 |
| 纯英文 | 英文 | 英文 |
| 英文讲述 · 双语字幕 | 英文 | 英文、中文 |
| 中文讲述 · 双语字幕 | 中文 | 中文、英文 |

**生词贴可独立开启或关闭**，四种语言预设都可以搭配，常规故事默认关闭。开启后，在对应台词出现时单独贴出英文单词、国际音标和中文释义。生词贴只用于画面，字幕和旁白继续使用所选语种。

**快捷预设「双语生词版」**直接选用英文旁白、中英双语字幕（英文在上）并开启生词贴，即《普罗米修斯》这一版的语言搭配。用户只说“双语字幕”时沿用中文旁白默认值；明确说“双语生词版”时用快捷预设。画风、配音工具和音乐仍按本次项目选择。

- **画风**：默认埃尔热欧洲清线漫画，可选探险活宝软线扁平、复古绘本、现代纪实、国风淡彩、黑白点睛、彩铅报刊漫画。以同一画风制作全片人物、背景与道具。
- **场景密度（多／中／少）**。与画风、逐笔分层分别选择。「多」每个分镜安排 2～3 个场景；「中」每个分镜安排 1～2 个场景，在转折处换场；「少」每个分镜集中在 1 个场景，相邻分镜可延续同一地点。一个场景应有明确的时空或独立布景与表演。仅换景别、推拉、切特写或显现新图层不另计场景。分镜表中按出场顺序写明子场景，按对应口播语义切换；交付前逐分镜核对数量。
- **逐笔分层（独立开关，默认关闭）**。七种画风都可选择。新项目仅在用户明确选择逐笔分层或使用对应快捷叫法时开启。单独选择任何画风均沿用常规动画。开启后按旁白节奏逐笔显现；关闭时沿用常规动画。只指定技法时沿用已选画风，新项目采用默认画风。「彩铅逐笔分层」同时选用彩铅报刊漫画并开启此项。
- **生图工具**：所有图片默认先调用系统自带的生图工具。仅当系统没有可用工具，或自带工具不支持该素材必需的原生透明输出时，询问用户“是否使用 LibTV 插件生成这些图片？”。收到明确同意后才可为这些图片建画布、上传参考图或发起 LibTV 生图。 图片按 `B*` / `C*` / `H*` 命名保存到 `assets/raw/`。
1. **画幅**：横版 `16:9`（1920×1080，B站/YouTube/公众号/大屏，**默认**）或竖版 `9:16`（1080×1920，抖音/小红书/视频号）。
2. **声音来源**：
   - **模式 A（使用 AI，默认 LibTV）**：按分场文案用 `libtv_story.py vo` 合成女声或男声，支持 `holds` 等旁白停顿。
   - **系统朗读**：用户不使用 AI 生成语音时，直接使用 macOS 已安装的对应语言声音。
   - **模式 B（真人录音）**：用户给一条现成口播音频或口播视频，后台自动识别断句与时间戳，动画严格跟他的语速走。
3. **出镜位（可选）**：
   - **全屏纯故事动画（默认，`host: null`）**：全画幅讲故事。
   - **2D IP 头像 / 半身像（`host.mode = "avatar"`）**：右下或左下角放主讲人，自动随配音包络张嘴说话，字幕自动避让。
   - **真人 / 数字人视频（`host.mode = "video"`）**：画面预留角落槽位与封面预览，最后由 `mix_voice.py --host-video` 合成画中画（圆形、圆角或绿幕抠像）。

---

### 1. 出故事台本，等用户确认（第一个关卡）

- 如果用户只给人物或主题：先快速检索核对关键年份、事实与转折点，写 5～8 场、总长约 50～90 秒的紧凑脚本。
- 如果用户已经给好台词或录音：按语义与情绪转折拆成 5～8 场，保留口语感；若先拿到了录音，可先跑建项目 + `voice_prep.py --from-recording` 把实际口播分段与每场起止秒数打印出来，再贴进台本里。
- 用一条消息给用户确认：
  - **故事梗概**与**核心物件**（片尾光圈可收拢成该物件剪影）
  - **分场表**：每场写地点、画面动作、口播台词（用 `[方括号]` 标出高亮关键词）、可选右上角信息卡（如 `1999年 · 华强北`）
  - 任意连续 8 秒内至少出现一次观众能辨认的场景或叙事重点变化。新地点、新动作、物件特写，以及把视线带到新主体的推拉都算（如从舟中人物带到江上明月）。仅在同一构图里轻微缩放或晃动不计。按最终配音时间轴复核首尾、阅读页和各切点之间的间隔。
  - 遇到典故、诗文或名句，在对应分镜标出篇名与出处，询问作者是否加文字，可选简短释义、原文节选或全文。作者已指定时直接执行。核对原文版本，按篇幅选用场内留白、半透明底板或片尾阅读页，避开人物与口播字幕，长文留出暂停阅读的稳定画面。
  - **角色表**与**画风**（见 `references/prompts.md` 七选一或用户指定），另列逐笔分层开关、场景密度及每个分镜的子场景
  - **画幅 / 旁白语种 / 字幕语种与顺序 / 生词贴开关及候选词 / 配音方案 / 是否加出镜位**
  - **预计消耗**：设定表 1 张 + 每场地 1 张背景 + 10～18 张角色姿势图，AI 配音每场 1 次

用户点头后建项目：
```bash
zsh <本 skill>/scripts/new_project.sh <项目目录> 16:9   # 默认横版 16:9；竖版传 9:16
```

---

### 2. 配音与字幕

按开工选择配置旁白语种、字幕与语音来源，英文、双语和系统朗读的字段与命令见 [语言和声音](references/languages.md)。

#### 路线 A：AI 配音
把各场台词写进 `assets/narration.json`（格式见 `assets/example-story/narration.json`），遇到多音字加 `"tts"` 字段写同音字替换，正文 `"zh"` 保持正确汉字：
```bash
cd <项目目录>
python3 <本 skill>/scripts/libtv_story.py init "<片名>"
python3 <本 skill>/scripts/libtv_story.py vo
$PY <本 skill>/scripts/voice_prep.py .
```
看 `voice_prep.py` 打印的「原稿 / 听写」对照：有念错或漏字，修改 `"tts"` 后只重跑该句 `libtv_story.py vo n3` 并重跑 `voice_prep.py`。

#### 路线 B：用户真人录音（或主讲人视频提音频）
```bash
# 若用户给的是口播视频，先规范化视频并提取音频：
$PY <本 skill>/scripts/prep_host_video.py <口播视频.mp4> <项目目录> --extract-voice

# 录音自动听写、对齐台本（可选 --transcript 传入每场一行的台本）、切分字幕并生成 30fps 口型包络：
$PY <本 skill>/scripts/voice_prep.py <项目目录> --from-recording <录音.mp3> [--transcript 台本.txt] [--scenes 6]
# 想保留画面“等旁白”的定格弹性时，额外加 --slice 切分成每场独立音频
```
记下终端打印的建议 `duration` 和 `sceneT`，写入 `page/story.js`。若启用了 `host`，想让字幕更紧凑可传 `--max-clause 16`。

---

### 3. 角色设定表，等用户看一眼（第二个关卡）

角色设定表、独立表演层、车马与船只、头像均须从生图阶段保留原生 Alpha 透明通道。检查深浅底上的轮廓、衣襟与车轮镂空；实底结果重新生成；分图按格裁切并原样保留 Alpha。

1. **优先调用系统自带生图工具**生成主角与关键配角的三视图/站姿设定表（`16:9`），开启透明背景参数（如 `transparent_background=true`），保存到 `assets/raw/char-sheet.png`（若后续需走 LibTV 回退，可再 `upload-sheet`）。
2. **仅当系统没有可生成原生透明 PNG 的生图工具且用户已明确同意时**，调用 LibTV：`libtv_story.py sheet "<角色设定表提示词>" 16:9`（若用户自带设定图且后续走 LibTV，用 `upload-sheet <路径>` 上传）。
3. 用 `read_file` 看图，确认角色辨识度、年代感与画风无误后发给用户看一眼。点头后再批量出后面所有图，避免返工。

---

### 4. 批量出背景、角色姿势、主讲人头像并测量原生透明素材

**逐镜分层是硬性要求。** 每场交付完整无人背景，每位出场人物独立生成透明角色层。可持握的道具可随姿势画在角色层；承担遮挡的牢门、栏杆、船舷等另设前景层，必要时把载具拆为前后两层夹住人物。按景深编排相对位移，保持脚点、坐面与接触处稳定。逐镜关闭人物层，核对背景完整且没有残留人物；单开每个角色检查轮廓、袖口和手部，再还原所有层看运动中的遮挡关系。交付可开关图层的工程或等效的可编辑分层工程。

1. **并行出图（默认优先使用系统自带生图工具；仅当系统缺少可生成原生透明 PNG 的工具且用户明确同意后，才调用 LibTV）**：
   - **默认路线（系统自带生图工具）**：
     - 每个场地 1 张背景空镜（无需透明）：用系统自带生图工具生成，保存为 `assets/raw/B1.png`、`B2.png` …
     - 每个动作瞬间 1 张角色姿势 / 独立道具 / 前景遮挡层（需原生透明 PNG）：若系统自带生图工具支持生成原生透明 PNG（如 `transparent_background=true`），传入角色设定表作为参考图生成，保存为 `assets/raw/C01.png`、`C02.png` …
     - 若选了 2D IP 主讲人出镜（需原生透明 PNG）：若系统自带生图工具支持透明 PNG，直接生成并保存为 `assets/raw/H_avatar.png`（`1:1`）。
   - **回退路线（仅当系统没有生图工具，或自带工具无法生成原生透明 PNG 并经用户明确同意后调用 LibTV）**：
     - 透明素材先确保已初始化画布并存在 `char-sheet`（可用 `libtv_story.py init` + `upload-sheet <本地设定表路径>` 或 `sheet`）
     - 角色姿势（自动连接 `char-sheet` 保持一致，直接生成透明 PNG）：`libtv_story.py pose C01 "<动作描述>" 3:4`
     - 2D IP 主讲人头像（直接生成透明 PNG）：`libtv_story.py host H_avatar "<头像或半身像描述>" 1:1`
     - 若系统完全无自带生图工具，经用户明确同意后背景空镜也可用 LibTV：`libtv_story.py bg B1 "<空镜描述>"`
   - **可选纯音乐 BGM**：`libtv_story.py bgm "<纯音乐描述>" assets/bgm.mp3`
2. **整理与质检**：
   ```bash
   $PY <本 skill>/scripts/fetch_assets.py <项目目录>
   $PY <本 skill>/scripts/contact_sheet.py <项目目录>
   ```
   打开 `build/联系表-抠图.jpg` 看三件事：边缘干净无绿边缺块、**手持道具结构连续**（不画断、不错握）、读出头顶刻度算出身高系数 `fact`。双人同图用 `split_sprite.py` 拆开。

---

### 5. 写 `page/story.js` 并抽帧自检

把表演写进 `page/story.js`，把路面、尺寸和机位标定写进 `page/blocking.json`。参考 `assets/example-story/story.js` 与 `references/production-notes.md`：
- **配音对齐**：`sceneT` 对应每场起点；AI 分句模式跑 `export_timeline.mjs` 检查重叠，有重叠就给该场加 `holds`；连续录音模式（`fullAudio`）直接按 `voice_prep.py` 给出的 `sceneT` 编排动画，`holds` 留空。
- **主讲人配置**：`host: null` 为全屏纯故事；开启时设为 `{ mode: "avatar", src: "../assets/host/H_avatar.png", pos: "right", frame: "circle", mouth: { x: 0.5, y: 0.62, s: 0.72 } }`（或 `mode: "video"`）。
- **转场默认静音。** 只有作者明确要求时，才在指定转场加入“呼呼”划过声（swish / whoosh）。要求增加切镜或运镜仅调整画面。续改旧工程时检查 `wipeCues`、手动音效事件和已有混音；若已有划过声，从音效分轨去除后再导出，保留旁白、配乐及其他现场音效。
- **运镜与动效**：按叙事焦点交替使用环境全景、双人中景、反应近景与关键道具特写；横移跟随、推近停住、拉远揭示环境各有落点。近景保留动作和视线所需空间，切姿势用 `puff` 烟团遮挡 + `squash` 弹跳，换场地默认 `transition: "auto"` 轮换多种转场。
- **抽帧检查**：
  ```bash
  cd <项目目录>
  export PLAYWRIGHT_MODULE=$PWD/node_modules/playwright
  node $CTV/scripts/preview.mjs page 8
  ```
  用 `read_file` 看 `page/build/preview.jpg`：确认角色脚和手持道具没被底部字幕或主讲人圆框挡住、信息卡文字清楚。

---

正式渲染前按 [走位与比例校正](references/blocking.md) 校准各镜头。用已标定的地面、人物和道具尺寸计算脚点与显示高度，逐张检查姿势图的肢体数量、连接和遮挡；步态循环与造型切换须放大检查完整周期或切换前后的逐帧局部图，确认袖口和手掌没有残影。执行 stage-audit.mjs 完成全镜头预检，校正后签入逐镜复核记录，再用 render_checked.sh 正式出片。

### 6. 渲染、混音与交付

```bash
cd <项目目录>
export PLAYWRIGHT_MODULE=$PWD/node_modules/playwright
node <本 skill>/scripts/export_timeline.mjs .
node <本 skill>/scripts/stage-audit.mjs .
# 查看逐镜画面和 motion.mp4，修正后填写与本次检查对应的 review.json
zsh <本 skill>/scripts/render_checked.sh "$PWD" "$PWD/build/v1"
$PY <本 skill>/scripts/mix_voice.py . build/v1/output/page.mp4 build/v1/mix-page.wav 成片/<片名>-v1.mp4 \
  [--bgm assets/bgm.mp3 --bgm-db -24] \
  [--host-video assets/host/video.mp4 --host-pos right --host-shape circle]
python3 $CTV/scripts/check_video.py 成片/<片名>-v1.mp4 --sheet 成片/联系表-v1.png
```
- 调试版式审查而不等整片渲染时，可加 `--fps 10 --samples 1` 先快速跑一轮检查；正式成片按默认 30fps + 子帧运动模糊渲染。
- 用 `read_file` 检查 `成片/联系表-v1.png` 确认无破图、无错位。
- 交付给用户：成片 MP4、所选语言 SRT、分层工程、画布链接（如有）与取舍说明（如替换的画面、是否经人耳试听确认音乐/配音比例）。
- 确认成片后清理 `build/` 渲染中间帧与 `assets/raw/` 原图（保留 `urls.txt` 与 `narration.json` 方便日后微调重渲）。
