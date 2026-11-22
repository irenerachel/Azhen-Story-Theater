// 示例人物故事：一米柜台（16:9 横版纯动画小剧场；改 host 为 avatar/video 即可开启右下角主讲人出镜）
const ASPECT = "16:9";
const [CW, CH] = ASPECT === "9:16" ? [1080, 1920] : [1920, 1080];
const IRIS0 = 37.5, IRIS1 = 38.9, ENDT = 39.1;

StoryVideo.init({
  aspect: ASPECT,
  label: "一米柜台",
  duration: 40,
  transition: "auto",
  music: { sound: "fpd-nostalgic-piano", gain_db: -27, fade_in: 0.4, fade_out: 1.5 },
  host: null,
  locs: [
    { id: "stall", bg: "B1", start: 0, end: 13.8, sprites: ["C01", "C02", "C03"] },
    { id: "rain", bg: "B2", start: 13.8, end: 27.0, sprites: ["C04", "C05"] },
    { id: "lab", bg: "B3", start: 27.0, end: 33.4, sprites: ["C06", "C07"] },
    { id: "stage", bg: "B4", start: 33.4, end: 40.0, sprites: ["C08"] },
  ],
  fact: { C01: 0.96, C02: 1.0, C03: 0.55, C04: 0.98, C05: 1.02, C06: 1.0, C07: 0.48, C08: 1.04 },
  ground: {
    stall: [420, 420, 790],
    rain: [410, 420, 790],
    lab: [450, 430, 800],
    stage: [430, 440, 800],
  },
  sceneT: [0, 7.0, 13.8, 20.6, 27.0, 33.4],
  holds: [],
  title: { loc: "stall", t1: "一米柜台", t2: "一九九九 · 华强北往事", x: 150, y: 120 },
  end: {
    irisStart: IRIS0,
    irisEnd: IRIS1,
    textAt: ENDT,
    text: "完",
    // 一枚芯片剪影作为片尾光圈
    path: "M-60 -60 L60 -60 L60 60 L-60 60 Z",
  },
});

const HERO_Y = 790;
const SWAP1 = 7.2, TITLE_OUT = 2.4;
C(SWAP1, "wz-impact-medium-soft", -3);

function drawStall(t) {
  const lc = "stall", fx = L[lc].fx, g = gAt(lc, HERO_Y);
  const z = lerp(1.0, 1.08, E.inOutCubic(P(t, 6.8, 7.4)));
  camera(lc, { z, fx: 960, fy: HERO_Y - g * 0.48, t });

  const tk = P(t, TITLE_OUT, TITLE_OUT + 0.45);
  TITLE.style.display = tk >= 1 ? "none" : "block";
  TITLE.style.transform = `translate(${-E.inCubic(tk) * 900}px,${-E.inCubic(tk) * 420}px) rotate(${-E.inCubic(tk) * 26}deg)`;

  if (t < SWAP1) {
    put(lc, "C01", { x: 1020, y: HERO_Y, h: SZ("C01", g) });
  } else {
    put(lc, "C02", { x: 1020, y: HERO_Y, h: SZ("C02", g), ...squash(t, SWAP1, 0.18) });
    put(lc, "C03", { x: 640, y: HERO_Y - 70, h: SZ("C03", gAt(lc, HERO_Y - 70)) });
  }
  puff(fx, t, SWAP1 - 0.25, 1020, HERO_Y - g * 0.45, g * 0.44, { dur: 0.9, seed: 11, n: 9 });
}

const DRY = 21.0;
C(14.3, "wz-impact-medium-soft", -2);
C(DRY, "wz-shimmer-short-sparkle", -4);

function drawRain(t) {
  const lc = "rain", fx = L[lc].fx, g = gAt(lc, HERO_Y);
  camera(lc, { z: lerp(1.0, 1.07, E.inOutCubic(P(t, 20.6, 21.2))), fx: 960, fy: HERO_Y - g * 0.5, dy: shake(t, 14.3, 12), t });
  if (t < DRY) {
    put(lc, "C04", { x: 960, y: HERO_Y, h: SZ("C04", g) });
  } else {
    put(lc, "C05", { x: 960, y: HERO_Y, h: SZ("C05", g), ...squash(t, DRY, 0.2) });
    twinkle(fx, t, DRY + 0.2, 960, HERO_Y - g * 0.72, 34, 0.65);
  }
  puff(fx, t, DRY - 0.2, 960, HERO_Y - g * 0.45, g * 0.45, { dur: 0.9, seed: 22, n: 10 });
}

const POP_BOARD = 28.0;
C(POP_BOARD, "wz-pop-large-out", -2);
C(POP_BOARD + 0.1, "wz-tone-ding-high", -4);

function drawLab(t) {
  const lc = "lab", fx = L[lc].fx, g = gAt(lc, HERO_Y);
  camera(lc, { z: lerp(1.0, 1.08, E.inOutCubic(P(t, 27.8, 28.4))), fx: 960, fy: HERO_Y - g * 0.48, t });
  put(lc, "C06", { x: 760, y: HERO_Y, h: SZ("C06", g) });
  if (t >= POP_BOARD) {
    put(lc, "C07", { x: 1220, y: HERO_Y - 80, h: SZ("C07", gAt(lc, HERO_Y - 80)), ...squash(t, POP_BOARD, 0.22) });
    twinkle(fx, t, POP_BOARD + 0.1, 1220, HERO_Y - 260, 42, 0.7);
  }
}

function drawStage(t) {
  const lc = "stage", fx = L[lc].fx, g = gAt(lc, HERO_Y);
  const cm = camera(lc, { z: lerp(1.0, 1.06, E.inOutCubic(P(t, 34.0, 34.6))), fx: 960, fy: HERO_Y - g * 0.55, t });
  put(lc, "C08", { x: 960, y: HERO_Y, h: SZ("C08", g), ...squash(t, 33.6, 0.15) });
  twinkle(fx, t, 35.0, 740, 420, 32, 0.7);
  twinkle(fx, t, 35.3, 1180, 460, 26, 0.7);
  setIrisFocus(cm.tx + 960 * cm.z, cm.ty + (HERO_Y - g * 0.78) * cm.z);
}

StoryVideo.start({ stall: drawStall, rain: drawRain, lab: drawLab, stage: drawStage });
