// 故事文件骨架：两个场地、两句中文旁白。复制后改配置、重写每个场地的绘制函数。
// 这里的时间都是“故事时间”（秒）。画面写在 CW×CH 的画布上：横版 1920×1080，竖版 1080×1920。
const ASPECT = "16:9";                             // new_project.sh 会改成建项目时选的画幅，要和 page/aspect.txt 一致
const [CW, CH] = ASPECT === "9:16" ? [1080, 1920] : [1920, 1080];
const IRIS0 = 14.6, IRIS1 = 15.9, ENDT = 16.1;      // 片尾：光圈开始收、收完、出片尾字

StoryVideo.init({
  aspect: ASPECT,
  label: "人物故事片名",
  duration: 17,                                    // 故事总长（秒，不含等旁白的停顿）
  transition: "auto",                              // 转场自动轮换（wipe / diagonal / iris / curtain / up）
  music: { sound: "fpd-nostalgic-piano", gain_db: -27, fade_in: 0.4, fade_out: 1.5 },
  // 可选主讲人出镜位：默认 null 为全屏纯故事动画；要主讲人出镜时取消注释并按需配置：
  // host: { mode: "avatar", src: "../assets/host/H_avatar.png", pos: "right", frame: "circle", mouth: { x: 0.5, y: 0.62, s: 0.72 } },
  // host: { mode: "video", poster: "../assets/host/poster.jpg", pos: "right", shape: "circle" },
  host: null,
  locs: [                                          // 每个场地一张背景 + 这个场地用到的精灵图（assets/cut/）
    { id: "scene1", bg: "B1", start: 0, end: 8, sprites: ["C01", "C02"] },
    { id: "scene2", bg: "B2", start: 8, end: 17, sprites: ["C05", "C08"] },
  ],
  fact: { C01: 0.98, C02: 1.04, C05: 0.85, C08: 1.0 },          // 身高表：显示高度 = 主角站立身高 × 系数
  ground: { scene1: [CH * 0.42, CH * 0.34, CH * 0.75], scene2: [CH * 0.43, CH * 0.32, CH * 0.73] },
  sceneT: [0, 8],                                  // 每句旁白从哪个故事时刻开始
  holds: [],                                       // 分句配音比画面长时加 [故事时刻, 增加秒数, 走速]；连续录音模式下保持 []
  title: { loc: "scene1", t1: "故事标题", t2: "一句副标题", x: CW * 0.08, y: CH * 0.1 },
  end: { irisStart: IRIS0, irisEnd: IRIS1, textAt: ENDT, text: "完",
    // 光圈形状：可换成故事代表物件的轮廓（原点为中心、约 200 宽，只用 M / L / C 绝对坐标）
    path: "M-100 0 C-100 -55 -55 -100 0 -100 C55 -100 100 -55 100 0 C100 55 55 100 0 100 C-55 100 -100 55 -100 0 Z" },
});

// ---------- 场地 1 ----------
const HERO = { x: CW * 0.58, y: CH * 0.73 };       // 脚位避开底部字幕（竖版 y<=1470，横版 y<=810）
const SWAP = 3.2, TITLE_OUT = 2.4;
C(SWAP, "wz-impact-medium-soft", -3);
function drawScene1(t) {
  const lc = "scene1", fx = L[lc].fx, g = gAt(lc, HERO.y);
  // 干脆的 0.6s 推镜：先静止，到点再快推到位
  const z = lerp(1.0, 1.08, E.inOutCubic(P(t, 2.6, 3.2)));
  camera(lc, { z, fx: HERO.x, fy: HERO.y - g * 0.5, t });
  const k = P(t, TITLE_OUT, TITLE_OUT + 0.45);
  TITLE.style.display = k >= 1 ? "none" : "block";
  TITLE.style.transform = `translate(${-E.inCubic(k) * CW * 0.6}px,${-E.inCubic(k) * CH * 0.35}px) rotate(${-E.inCubic(k) * 26}deg)`;
  if (t < SWAP) put(lc, "C01", { x: HERO.x + Math.sin(t * 7) * 6, y: HERO.y, h: SZ("C01", g), flip: true });
  else put(lc, "C02", { x: HERO.x, y: HERO.y, h: SZ("C02", g), ...squash(t, SWAP, 0.2) });
  puff(fx, t, SWAP - 0.3, HERO.x, HERO.y - g * 0.5, g * 0.5, { dur: 0.95, seed: 7, n: 10 });
}

// ---------- 场地 2 ----------
const POP = 8.9, ZAP = 12.0;
C(POP, "wz-pop-large-out", -2); C(ZAP, "wz-shimmer-short-sparkle", -5);
function drawScene2(t) {
  const lc = "scene2", fx = L[lc].fx, y = CH * 0.72, g = gAt(lc, y), ax = CW * 0.28, bx = CW * 0.72;
  const cm = camera(lc, { z: lerp(1.06, 1.0, E.outCubic(P(t, 8, 8.6))), fx: CW / 2, fy: CH * 0.55, t });
  put(lc, "C08", { x: bx, y, h: SZ("C08", g) });
  if (t >= POP + 0.25) put(lc, "C05", { x: ax, y: y + 20, h: SZ("C05", gAt(lc, y + 20)), ...squash(t, POP + 0.25, 0.2) });
  puff(fx, t, POP, ax, y - g * 0.3, g * 0.4, { dur: 0.9, seed: 200, fill: "#F7F1E4", n: 9 });
  zap(fx, t, ZAP, ax + g * 0.25, y - g * 0.65, bx, y - g * 0.6);
  setIrisFocus(cm.tx + bx * cm.z, cm.ty + (y - g * 0.8) * cm.z);
}

StoryVideo.start({ scene1: drawScene1, scene2: drawScene2 });
