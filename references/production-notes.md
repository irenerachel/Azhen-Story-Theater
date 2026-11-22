# 制作要点与引擎接口

## 目录
1. 故事文件结构与引擎接口
2. 主讲人出镜位（头像 / 视频）与安全区坐标
3. 连续口播录音 vs 分句配音的对齐方式
4. 角色比例 `fact` 与地面透视 `ground`
5. 转场、运镜与版式审查红线
6. 渲染、混音与清理

---

## 1. 故事文件结构与引擎接口

动画由两层组成：`lib/engine.js`（通用引擎，不改）和 `page/story.js`（本片配置与场景绘制）。`page/narration.js` 由 `voice_prep.py` 自动生成。

```js
StoryVideo.init({
  aspect, label, duration, transition, music, host,
  locs, fact, ground, sceneT, holds, title, end
});
function drawScene1(t) { ... }
StoryVideo.start({ scene1: drawScene1, ... });
```

`init` 之后可用的全局工具：

| 名称 | 作用 |
|---|---|
| `W` `H` | 画布宽高：竖版 `1080×1920`，横版 `1920×1080` |
| `put(场地, 图名, {x, y, h, flip, rot, skew, sx, sy, ox, oy, z})` | 按脚底 `(x, y)` 摆精灵图；`y` 越大越靠前，自动排遮挡 |
| `SZ(图名, g)` `gAt(场地, 脚y)` | 身高表与地面透视换算 |
| `camera(场地, {z, fx, fy, dx, dy, t, drift})` | 推拉镜头，不露背景边；`drift` 默认 `0` 避免慢速文字抖动 |
| `squash(t, t0, 幅度)` | 落位挤压回弹，展开进 `put` |
| `puff(fx, t, t0, x, y, 半径, {dur, seed, fill, n, drift})` | 手绘沸腾线烟尘云，用来遮住换姿势或制造出场尘土 |
| `star` `twinkle` `zap` `speed` | 星光、闪烁、轨迹飞星、速度线 |
| `shake(t, t0, 幅度)` | 震动偏移，加到 `camera` 的 `dx / dy` 上 |
| `C(故事时刻, 音效编号, 音量dB)` | 声音提示（音效编号用 `python3 $CTV/scripts/sound_library.py search` 查） |
| `L[场地].fx` | 当前场地 SVG 特效层 |
| `TITLE` | 标题牌 DOM 元素，自行写离场动画（若要移动它，在 2.0s 后再飞出或立即 `display="none"`，避免在落位检查帧半截压边） |
| `makeInset(场地, 图名, {left, top, size})` | 放大圆框特写细节 |
| `setIrisFocus(x, y)` | 片尾光圈收拢焦点（屏幕坐标，由 `camera` 返回值换算） |

---

## 2. 主讲人出镜位（头像 / 视频）与安全区坐标

### `host` 配置写法
- **全屏纯故事（默认）**：`host: null`
- **2D IP 说话头像**：
  ```js
  host: {
    mode: "avatar",
    src: "../assets/host/H_avatar.png",
    pos: "right",          // "right" 或 "left"
    frame: "circle",       // "circle" 圆形头像框；"bust" 无边框半身立绘
    mouth: { x: 0.50, y: 0.62, s: 0.72 },  // 可选：嘴巴在图里的归一化坐标；也可改传 srcTalk 换嘴型图
    // ranges: [[0, 6], [42, 50]],         // 可选：只在片头/片尾露脸
  }
  ```
- **真人 / 数字人口播视频**：
  ```js
  host: {
    mode: "video",
    poster: "../assets/host/poster.jpg",   // 抽帧预览时占位显示；由 prep_host_video.py 生成
    pos: "right",
    shape: "circle",                       // "circle" | "rounded" | "cutout"（绿幕抠像）
  }
  ```
  注意：`mode: "video"` 在浏览器里只负责让字幕框自动避让并显示静态封面预览；真正的视频画中画合成在 `mix_voice.py --host-video ...` 完成。

### 画面安全区（人物脚位与关键道具务必放高于此线）
| 画幅 | 模式 | 底部字幕占用区 | 建议人物最高脚位 `y` | 右上角信息卡 `#scard` 占用区 |
|---|---|---|---|---|
| 横版 `16:9`（默认） | 无主讲人 | 居中 `y ≈ 820～1008` | `y <= 800` | `x >= 1200, y ≈ 88～300` |
| 横版 `16:9`（默认） | 有主讲人（右侧） | 左侧 `x: 110～1550, y ≈ 820～1008`；头像 `x: 1624～1844` | `y <= 800` | 同上 |
| 竖版 `9:16` | 无主讲人 | 居中 `y ≈ 1500～1710` | `y <= 1450` | `x >= 490, y ≈ 180～420` |
| 竖版 `9:16` | 有主讲人（右侧） | 左侧 `x: 76～764, y ≈ 1500～1710`；头像 `x: 808～1008` | `y <= 1450` | 同上 |

---

## 3. 连续口播录音 vs 分句配音的对齐方式

1. **分句模式（AI 配音，或 `voice_prep.py --from-recording ... --slice`）**：
   - 每场一句独立音频 `n1.mp3, n2.mp3...`。
   - 若某场配音比画面动作长，`export_timeline.mjs` 会报警；此时在动作已经落定的时刻插入 `holds: [[故事时刻, 增加秒数, 停顿走速]]`（走速 `0.08` 接近定格呼吸），让画面等旁白。
2. **连续录音模式（`voice_prep.py --from-recording` 默认不加 `--slice`）**：
   - `narration.json` 带 `fullAudio` 与每句的 `origStart` / `origEnd`，完整保留真人说话的气口和环境音，不切碎音频。
   - **此时 `holds` 必须保持 `[]`**（因为整条音轨不能中途拉伸），`sceneT` 直接填入 `voice_prep.py` 输出的各句 `origStart`，让画面事件踩准真实讲话时刻。

---

## 4. 角色比例 `fact` 与地面透视 `ground`

1. 运行 `contact_sheet.py` 出带 5% 刻度的 `build/联系表-抠图.jpg`。
2. 设主角站立身高为 `1`（配角按实际比例设，如大人 `1.0`、小孩 `0.65`、桌椅道具 `0.45`）。
3. 读出某张图里主体头顶刻度 `p_top` 和脚底刻度 `p_bot`：
   - 人占图高比例 `ratio = (p_bot - p_top) / 100`
   - `fact[图名] = 角色相对身高 / ratio`
4. `ground[场地] = [地平线 y, 参考主角身高, 参考脚位 y]`，`gAt(场地, y)` 自动给出景深透视身高。

---

## 5. 转场、运镜与版式审查红线

- **转场**：`transition: "auto"` 默认在 `wipe`（横扫）、`diagonal`（斜切）、`iris`（圆孔扩散）、`curtain`（幕布中分）、`up`（自下而上）之间轮换，相邻两场不重复；单场也可写 `transition: "cut"` 硬切或 `"clock"` 时针扫屏。
- **运镜**：先决定观众该看谁、看哪个动作，再选择固定近景、过肩切换、横移跟随、推近停住或拉远揭示。按主体、远景和前景分别计算视差；检查起止构图与移动中点，字幕固定在屏幕坐标。
- **渲染器版式审查（`render_page.mjs` 硬规则）**：
  - 禁止在任何 DOM 元素上写 `box-shadow` 或 `text-shadow`（用实线 `border` 替代）。
  - 自定义 `palette` 时，文字前景色与底色对比度必须 `>= 4.5:1`（推荐深墨 `#2B2320` / 砖红 `#A63E14` 配米白 `#F3EAD6`）。
  - 所有带 `data-box` 或 `data-read` 的可见文字块，距画布四边不小于画布短边的 6%（竖版底边不小于 12%）。

---

## 6. 渲染、混音与清理

- 确认成片后清理：`build/`（保留 `narration.json`、`story.js` 和 `urls.txt`）、`assets/raw/`（需要重下可凭 `urls.txt` 或重生成），旧版成片询问用户后再删。
- 若使用了 BGM 与音效自动混音，交付说明里写明是否经过人耳试听调整 `--bgm-db`。
