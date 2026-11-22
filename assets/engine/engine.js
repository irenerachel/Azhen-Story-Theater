// 故事小剧场动画引擎：所有故事通用，不要在这里写任何故事专属的内容。
// 负责：画布与样式、场地图层、精灵摆放与前后排序、身高表与地面透视、烟团/星光/速度线、镜头、
//       “等旁白”时间重映射、连续口播/分句字幕、可选故事信息卡、可选主讲人出镜位（头像/口型/视频预留）、
//       多种转场、片尾光圈、声音提示、渲染器约定。
// 用法（story.js）：
//   StoryVideo.init({ ...配置 });     // 之后 put / puff / camera / C / gAt 等都是全局函数
//   function drawScene1(t) { ... }    // 每个场地一个绘制函数，t 是故事时间
//   StoryVideo.start({ scene1: drawScene1, ... });
// 依赖：gsap、demo.js、fx.js（先于本文件加载）；narration.js 提供 window.NARRATION。
(() => {
  const NS = "http://www.w3.org/2000/svg";
  const SIZES = { "16:9": [1920, 1080], "9:16": [1080, 1920] };
  const TRANS_POOL = ["wipe", "diagonal", "iris", "curtain", "up"];
  const SV = (window.StoryVideo = window.VocabStory = {});

  SV.init = (cfg) => {
    const [W, H] = SIZES[cfg.aspect || "16:9"] || (() => { throw new Error(`不支持的画幅 ${cfg.aspect}`); })();
    const tall = H > W;
    const pal = cfg.palette || {};
    const INK = pal.ink || "#2B2320";
    const CREAM = pal.cream || "#F3EAD6";
    const GOLD = pal.gold || "#F4D58D";
    const ACCENT = pal.accent || "#A63E14";
    const DUST = pal.dust || "#D9CDB8";
    const SUBTEXT = pal.subtext || "#4A3C34";
    const { E, lerp, spring, clamp } = FX;
    const P = (t, a, b) => clamp((t - a) / (b - a));
    const hash = (n) => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
    const DUR = cfg.duration;
    const HOST = cfg.host || null;

    // ---------- 字幕框、故事卡与可选主讲人槽位几何 ----------
    // 严格遵守 render_page.mjs 版式审查：边缘安全距 >= 6% min(W,H) (=64.8px)，竖版底边距 >= 12% (=129.6px)；禁止任何 box-shadow / text-shadow
    const hostPos = (HOST && HOST.pos) || "right";
    const hostSize = HOST ? (HOST.size || (tall ? 200 : 220)) : 0;
    const hostFrame = HOST ? (HOST.frame || "circle") : "circle";
    const hostMarginX = tall ? 72 : 76;
    const hostBottom = tall ? 205 : 72;
    const hostGap = tall ? 44 : 74;

    const sub = !HOST
      ? (tall
          ? { centerX: W / 2, bottom: 210, maxW: 920, zhSize: 38, enSize: 28 }
          : { centerX: W / 2, bottom: 72, maxW: 1640, zhSize: 38, enSize: 28 })
      : (tall
          ? {
              centerX: hostPos === "right"
                ? Math.round((76 + (W - hostMarginX - hostSize - hostGap)) / 2)
                : Math.round((hostMarginX + hostSize + hostGap + (W - 76)) / 2),
              bottom: 210,
              maxW: W - 76 - hostMarginX - hostSize - hostGap,
              zhSize: 34,
              enSize: 26,
            }
          : {
              centerX: hostPos === "right"
                ? Math.round((110 + (W - hostMarginX - hostSize - hostGap)) / 2)
                : Math.round((hostMarginX + hostSize + hostGap + (W - 110)) / 2),
              bottom: 72,
              maxW: W - 110 - hostMarginX - hostSize - hostGap,
              zhSize: 38,
              enSize: 28,
            });

    const sc = tall ? { right: 72, top: 180, maxW: 520 } : { right: 100, top: 88, maxW: 620 };
    const titleDef = {
      x: tall ? 84 : 150,
      y: tall ? 180 : 120,
      t1Size: tall ? 104 : 156,
      t2Size: tall ? 38 : 48,
      pad: tall ? "28px 54px 32px" : "34px 70px 40px",
      maxW: W - (tall ? 168 : 300),
    };

    const hostBox = HOST ? {
      mode: HOST.mode || "avatar",
      pos: hostPos,
      frame: hostFrame,
      shape: HOST.shape || (hostFrame === "bust" ? "cutout" : "circle"),
      size: hostSize,
      width: hostSize,
      height: hostFrame === "bust" ? Math.round(hostSize * 1.25) : hostSize,
      x: hostPos === "right" ? W - hostMarginX - hostSize : hostMarginX,
      y: H - hostBottom - (hostFrame === "bust" ? Math.round(hostSize * 1.25) : hostSize),
      bottom: hostBottom,
      marginX: hostMarginX,
    } : null;

    const css = document.createElement("style");
    css.textContent = `
@font-face{font-family:"ChillRound";src:url("../assets/fonts/ChillRoundGothic/ChillRoundGothic_Medium.ttf") format("truetype");font-weight:400 500;font-display:block}
@font-face{font-family:"ChillRound";src:url("../assets/fonts/ChillRoundGothic/ChillRoundGothic_Bold.ttf") format("truetype");font-weight:600 900;font-display:block}
:root{--ink:${INK};--cream:${CREAM};--gold:${GOLD};--accent:${ACCENT};--subtext:${SUBTEXT}}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:${W}px;height:${H}px;overflow:hidden;background:${INK}}
body{font-family:"ChillRound",sans-serif;font-weight:500;color:var(--ink)}
.loc{position:absolute;inset:0;overflow:hidden;display:none}
.cam{position:absolute;left:0;top:0;width:${W}px;height:${H}px;transform-origin:0 0}
.cam>img.bg{position:absolute;left:0;top:0;width:${W}px;height:${H}px;object-fit:cover}
.spr{position:absolute;left:0;top:0;display:none}
svg.fx{position:absolute;left:0;top:0;width:${W}px;height:${H}px;overflow:visible;z-index:5000}
#title{position:absolute;background:var(--cream);border:5px solid var(--ink);
  border-radius:46px 24px 52px 20px;padding:${titleDef.pad};max-width:${titleDef.maxW}px;transform-origin:50% 50%}
#title .t1{font-weight:700;font-size:${titleDef.t1Size}px;line-height:1.22;letter-spacing:0.05em;color:var(--ink)}
#title .t2{font-size:${titleDef.t2Size}px;line-height:1.4;margin-top:8px;color:var(--subtext)}
#sub{position:absolute;left:${sub.centerX}px;bottom:${sub.bottom}px;transform:translateX(-50%);background:var(--cream);border:4px solid var(--ink);
  border-radius:22px 14px 26px 12px;padding:24px 44px 26px;width:max-content;max-width:${sub.maxW}px;text-align:center;opacity:0}
#sub .zh{font-weight:600;font-size:${sub.zhSize}px;line-height:1.42;color:var(--ink);text-wrap:balance}
#sub .en{font-family:"Fraunces",serif;font-weight:600;font-size:${sub.enSize}px;line-height:1.36;color:var(--subtext);margin-top:6px;text-wrap:balance;display:none}
#sub .hi{color:var(--accent);text-decoration:underline wavy #C9772B;text-decoration-thickness:3px;text-underline-offset:7px}
#scard{position:absolute;right:${sc.right}px;top:${sc.top}px;background:var(--cream);border:4px solid var(--ink);border-radius:26px 16px 30px 14px;
  padding:28px 50px 30px;opacity:0;transform-origin:85% 0%;min-width:280px;max-width:${sc.maxW}px}
#scard .tag{font-size:24px;line-height:1.35;color:var(--subtext)}
#scard .title{font-weight:700;font-size:44px;line-height:1.28;color:var(--accent);margin-top:4px;text-wrap:balance}
#scard .sub{font-size:30px;line-height:1.42;color:var(--ink);margin-top:6px;text-wrap:balance}
#hostCv{position:absolute;pointer-events:none;z-index:125;display:none}
#over{position:absolute;inset:0;width:${W}px;height:${H}px;pointer-events:none}
#over{z-index:100}#end{z-index:110}#sub{z-index:120}#scard{z-index:120}
.inset{position:absolute;border-radius:50%;overflow:hidden;border:6px solid var(--ink);background:#E9D9BC;display:none;z-index:50}
.inset img{position:absolute}
#end{position:absolute;inset:0;display:none;align-items:center;justify-content:center;background:var(--ink)}
#end span{font-weight:700;font-size:${tall ? 168 : 220}px;color:var(--cream);line-height:1.2;display:inline-block}`;
    document.head.append(css);
    document.body.insertAdjacentHTML("afterbegin", `<div id="locs"></div>
<div id="sub" data-box><div class="zh" data-text id="subZh"></div><div class="en" data-text id="subEn"></div></div>
<div id="scard" data-box><div class="tag" data-text id="st"></div><div class="title" data-text id="sw"></div><div class="sub" data-text id="sm"></div></div>
<canvas id="hostCv"></canvas>
<svg id="over" viewBox="0 0 ${W} ${H}"></svg>
<div id="end"><span data-read id="endt"></span></div>`);
    const over = document.getElementById("over");

    // ---------- 时间重映射：在动作已落定的地方放慢“等旁白”，配音不变速 ----------
    // holds: [故事时刻, 增加的视频秒数, 停顿内故事走速]
    const NAR = cfg.narration || window.NARRATION || { lines: [] };
    const FULL_AUDIO = Boolean(NAR.fullAudio);
    const HOLDS = ((FULL_AUDIO && !cfg.allowHoldsOnFullAudio) ? [] : (cfg.holds || [])).map(([s0, e, r]) => ({ s0, L: e / (1 - r), r }));
    const storyOf = (T) => { let off = 0; for (const h of HOLDS) { const Ts = h.s0 + off; if (T < Ts) return T - off; if (T < Ts + h.L) return h.s0 + h.r * (T - Ts); off += h.L * (1 - h.r); } return T - off; };
    const videoOf = (t) => { let off = 0; for (const h of HOLDS) { if (t <= h.s0) return t + off; if (t < h.s0 + h.r * h.L) return h.s0 + off + (t - h.s0) / h.r; off += h.L * (1 - h.r); } return t + off; };
    const VDUR = Math.round(videoOf(DUR) * 30) / 30;
    const D = Demo({ duration: VDUR, label: cfg.label || "", music: cfg.music || null });
    let VB = 0;
    { const seek0 = window.__seek; window.__seek = (T, b = T) => { VB = b; seek0(storyOf(T), storyOf(b)); }; }
    window.__scene.motion_blur = cfg.motionBlur || { samples: 5, shutter: 0.5 };
    window.__scene.finish = cfg.finish || { grain: 0.03, vignette: 0.18 };
    const C = (t, s, g = 0) => D.cue(videoOf(t), s, g);

    // ---------- 场地与素材 ----------
    const LOCS = cfg.locs, WIPE = cfg.wipe ?? 0.65;
    const L = {}, AR = {}, loads = window.stagePlanReady ? [window.stagePlanReady] : [];
    for (const loc of LOCS) {
      const box = document.createElement("div"); box.className = "loc"; box.id = "L_" + loc.id;
      const cam = document.createElement("div"); cam.className = "cam";
      const bg = document.createElement("img"); bg.className = "bg"; bg.src = `../assets/bg/${loc.bg}.jpg`; cam.append(bg); loads.push(bg.decode());
      const spr = {};
      for (const n of (loc.sprites || [])) {
        const im = document.createElement("img"); im.className = "spr"; im.src = `../assets/cut/${n}.png`; cam.append(im); spr[n] = im;
        loads.push(im.decode().then(() => { AR[n] = im.naturalWidth / im.naturalHeight; }));
      }
      const fx = document.createElementNS(NS, "svg"); fx.setAttribute("class", "fx"); fx.setAttribute("viewBox", `0 0 ${W} ${H}`); cam.append(fx);
      box.append(cam); document.getElementById("locs").append(box);
      L[loc.id] = { ...loc, el: box, cam, spr, fx };
    }

    // 标题牌：放在指定场地里，随场地一起被转场擦掉；故事里通过 TITLE 做动画
    let TITLE = null;
    if (cfg.title) {
      TITLE = document.createElement("div"); TITLE.id = "title";
      TITLE.style.left = (cfg.title.x ?? titleDef.x) + "px"; TITLE.style.top = (cfg.title.y ?? titleDef.y) + "px";
      const t1 = document.createElement("div"); t1.className = "t1"; t1.dataset.read = ""; t1.textContent = cfg.title.t1;
      if (cfg.title.size) t1.style.fontSize = cfg.title.size + "px";
      TITLE.append(t1);
      if (cfg.title.t2) {
        const t2 = document.createElement("div"); t2.className = "t2"; t2.dataset.read = ""; t2.textContent = cfg.title.t2;
        TITLE.append(t2);
      }
      L[cfg.title.loc].el.append(TITLE);
    }

    // 主讲人头像 / 静态预览加载
    const hostCv = document.getElementById("hostCv");
    const hostCtx = hostCv.getContext("2d");
    const hostImgs = { main: null, talk: null };
    if (HOST && hostBox) {
      const dpr = 2;
      hostCv.width = hostBox.width * dpr;
      hostCv.height = hostBox.height * dpr;
      hostCv.style.width = hostBox.width + "px";
      hostCv.style.height = hostBox.height + "px";
      hostCv.style.left = hostBox.x + "px";
      hostCv.style.top = hostBox.y + "px";
      hostCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const mainSrc = hostBox.mode === "video" ? HOST.poster : HOST.src;
      if (mainSrc) {
        const im = new Image(); im.src = mainSrc;
        loads.push(im.decode().then(() => { hostImgs.main = im; }));
      }
      if (HOST.srcTalk) {
        const im2 = new Image(); im2.src = HOST.srcTalk;
        loads.push(im2.decode().then(() => { hostImgs.talk = im2; }));
      }
    }

    // 放大圆框：特写被字幕挡住或太小的细节
    const makeInset = (loc, sprite, { left, top, size }) => {
      const d = document.createElement("div"); d.className = "inset";
      d.style.cssText += `left:${left}px;top:${top}px;width:${size}px;height:${size}px`;
      d.innerHTML = `<img src="../assets/cut/${sprite}.png">`; L[loc].el.append(d); return d;
    };
    window.__ready = Promise.all([document.fonts.ready, ...loads]);

    // ---------- 绘制工具 ----------
    function put(loc, n, o) {
      const im = L[loc].spr[n];
      if (window.stagePlan) o = stagePlacement(window.stagePlan,loc,n,storyOf(VB),o);
      im._stagePose = o;
      const h = o.h, w = h * AR[n];
      const ox = o.ox ?? 0.5, oy = o.oy ?? 1;
      im.style.display = "block"; im.style.width = w + "px"; im.style.height = h + "px";
      im.style.opacity = o.op ?? 1; im.style.zIndex = String(Math.round(o.y + (o.z || 0)));
      im.style.transformOrigin = `${w * ox}px ${h * oy}px`;
      im.style.transform = `translate(${o.x - w * ox}px,${o.y - h * oy}px) rotate(${o.rot || 0}deg) skewX(${o.skew || 0}deg) scale(${(o.sx ?? 1) * (o.flip ? -1 : 1)},${o.sy ?? 1})`;
      return { w, h, left: o.x - w * ox, top: o.y - h * oy };
    }
    const FACT = cfg.fact || {};
    const SZ = (n, g) => { if (!(n in FACT)) throw new Error(`身高表 fact 里没有 ${n}`); return g * FACT[n]; };
    const GROUND = cfg.ground || {};
    const gAt = (loc, y) => { const [hz, g0, y0] = GROUND[loc]; return g0 * (y - hz) / (y0 - hz); };
    function squash(t, t0, amt = 0.16) {
      if (t < t0) return { sx: 1, sy: 1 };
      const v = spring(t - t0, 3.0, 0.42); const d = (1 - v) * amt;
      return { sx: 1 + d * 0.7, sy: 1 - d };
    }
    function el(svg, tag, attrs) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); svg.append(e); return e; }
    function puff(svg, t, t0, cx, cy, R, { dur = 0.9, seed = 1, fill = DUST, n = 8, drift = [0, 0] } = {}) {
      const k = (t - t0) / dur; if (k < 0 || k > 1) return;
      const g = E.outBack(clamp(k / 0.28), 1.6);
      const boil = Math.floor(t * 10);
      const blobs = [];
      for (let i = 0; i <= n; i++) {
        const a = (i / n) * Math.PI * 2 + hash(seed + i) * 0.6;
        const center = i === n;
        const dist = center ? 0 : R * 0.52 * g;
        const shrink = clamp((k - 0.42 - (center ? 0.12 : hash(seed * 3 + i) * 0.18)) / 0.32);
        const r = R * (center ? 0.55 : 0.36 + hash(seed * 7 + i) * 0.16) * g * (1 - E.inCubic(shrink));
        if (r < 1) continue;
        const jx = (hash(boil * 13 + i + seed) - 0.5) * 5, jy = (hash(boil * 29 + i + seed) - 0.5) * 5;
        blobs.push([cx + Math.cos(a) * dist + jx + drift[0] * k, cy + Math.sin(a) * dist * 0.8 + jy + drift[1] * k, r]);
      }
      const sw = 4.5;
      for (const [x, y, r] of blobs) el(svg, "circle", { cx: x, cy: y, r: r + sw, fill: INK });
      for (const [x, y, r] of blobs) el(svg, "circle", { cx: x, cy: y, r, fill });
      for (const [x, y, r] of blobs.slice(0, 3)) if (r > 30)
        el(svg, "path", { d: `M${x - r * 0.4} ${y + r * 0.1} q${r * 0.3} ${-r * 0.35} ${r * 0.6} ${-r * 0.05}`, fill: "none", stroke: INK, "stroke-width": 3, "stroke-linecap": "round" });
    }
    function star(svg, x, y, s, rot = 0, fill = GOLD) {
      if (s <= 0.5) return;
      const q = s * 0.26;
      el(svg, "path", { d: `M0 ${-s} L${q} ${-q} L${s} 0 L${q} ${q} L0 ${s} L${-q} ${q} L${-s} 0 L${-q} ${-q} Z`, fill, stroke: INK, "stroke-width": 3, "stroke-linejoin": "round", transform: `translate(${x} ${y}) rotate(${rot})` });
    }
    function twinkle(svg, t, t0, x, y, s, dur = 0.5) {
      const k = (t - t0) / dur; if (k < 0 || k > 1) return;
      star(svg, x, y, s * Math.sin(Math.PI * k), k * 90);
    }
    function speed(svg, t, x, y, ang, len, n, spread, seed = 1, w = 3) {
      const boil = Math.floor(t * 10);
      const dx = Math.cos(ang), dy = Math.sin(ang), nx = -dy, ny = dx;
      for (let i = 0; i < n; i++) {
        const off = (i / (n - 1) - 0.5) * spread + (hash(boil + i * 7 + seed) - 0.5) * 18;
        const l = len * (0.55 + hash(seed + i * 3) * 0.45);
        const sx = x + nx * off + dx * hash(i + seed) * 30, sy = y + ny * off + dy * hash(i + seed) * 30;
        el(svg, "line", { x1: sx, y1: sy, x2: sx + dx * l, y2: sy + dy * l, stroke: INK, "stroke-width": w, "stroke-linecap": "round" });
      }
    }
    function zap(svg, t, t0, ax, ay, bx, by, dur = 0.4) {
      const k = (t - t0) / dur; if (k < 0 || k > 1.25) return;
      for (let i = 0; i < 7; i++) {
        const u = clamp(k - i * 0.05); if (u <= 0) continue;
        const e = E.inOutCubic(u);
        const x = lerp(ax, bx, e), y = lerp(ay, by, e) - Math.sin(Math.PI * e) * 120;
        const fade = 1 - clamp((k - 1) / 0.25);
        star(svg, x, y, (16 - i * 1.8) * fade, t * 300 + i * 40);
      }
    }
    // 摄像机：z 缩放，围绕焦点 (fx,fy)，默认不抖动（drift = 0），并限制不露出背景边缘
    function camera(loc, { z = 1, fx = W / 2, fy = H / 2, dx = 0, dy = 0, t = 0, drift = cfg.cameraDrift ?? 0 } = {}) {
      let tx = W / 2 - fx * z + dx, ty = H / 2 - fy * z + dy;
      if (drift > 0) {
        tx += (FX.fbm(t * 0.5, 1.3) - 0.5) * drift * 2;
        ty += (FX.fbm(4.1, t * 0.5) - 0.5) * drift * 2;
      }
      tx = Math.min(0, Math.max(W - W * z, tx)); ty = Math.min(0, Math.max(H - H * z, ty));
      L[loc].cam.style.transform = `translate(${tx}px,${ty}px) scale(${z})`;
      return { z, tx, ty };
    }
    const shake = (t, t0, amp = 14) => t < t0 ? 0 : amp * Math.exp(-9 * (t - t0)) * Math.sin((t - t0) * 70);

    // ---------- 字幕 + 故事信息卡 + 配音包络 ----------
    const LINES = (NAR.lines || []).map((l) => ({ ...l }));
    const SCENE_T = cfg.sceneT || LINES.map((l, i) => l.origStart ?? i * 6);
    if (LINES.length && SCENE_T.length !== LINES.length) throw new Error(`sceneT 有 ${SCENE_T.length} 项，旁白有 ${LINES.length} 句，必须一一对应`);

    const SUBS = [];
    const CARDS = [];
    const VOCAB = NAR.vocab || {};
    LINES.forEach((l, i) => {
      if (!l.dur) throw new Error(`旁白 ${l.id} 没有 dur，先运行 voice_prep.py`);
      if (FULL_AUDIO) {
        l.start = l.origStart ?? videoOf(SCENE_T[i]);
        l.end = l.origEnd ?? (l.start + l.dur);
      } else {
        l.start = videoOf(SCENE_T[i]) + (i === 0 ? 0.45 : 0.3);
        const nextStart = i < LINES.length - 1 ? videoOf(SCENE_T[i + 1]) + 0.08 : VDUR - 0.35;
        l.end = Math.min(l.start + l.dur + 0.75, nextStart);
        if (l.start + l.dur > nextStart + 0.05) console.warn(`旁白 ${l.id} 比这一场长 ${(l.start + l.dur - nextStart).toFixed(2)} 秒，会和下一句重叠：给这一场加 holds`);
      }

      const zhText = l.zh || "";
      const enText = l.en || "";
      if (Array.isArray(l.clauses) && l.clauses.length > 0) {
        l.clauses.forEach((c, ci) => {
          const cs = l.start + (c.offset || 0);
          const nextCs = ci < l.clauses.length - 1 ? l.start + (l.clauses[ci + 1].offset || 0) - 0.04 : l.end;
          const ce = Math.min(l.end, nextCs, cs + (c.dur || 2.0) + 0.2);
          SUBS.push({ start: cs, end: Math.max(cs + 0.25, ce), zh: c.text || "", en: c.en || "" });
        });
      } else if (zhText || enText) {
        SUBS.push({ start: l.start, end: l.end, zh: zhText, en: enText });
      }

      // 故事信息卡：支持 line.card / line.cards；若仍沿用 vocab [词] 也兼容
      const rawCards = Array.isArray(l.cards) ? l.cards : (l.card ? [l.card] : []);
      const timed = l.words || {};
      if (!rawCards.length && Object.keys(VOCAB).length && enText) {
        const plain = enText.replace(/[\[\]]/g, "");
        enText.replace(/\[([^\]]+)\]/g, (m, w, off) => {
          if (VOCAB[w]) {
            const pos = enText.slice(0, off).replace(/[\[\]]/g, "").length;
            const at = w in timed ? l.start + Math.max(0, timed[w] - 0.1) : l.start + 0.15 + (pos / Math.max(1, plain.length)) * Math.max(0.4, l.dur - 0.3);
            rawCards.push({ tag: VOCAB[w][0], title: w, sub: VOCAB[w][1], _at: at });
          }
          return m;
        });
      }
      rawCards.forEach((c, ci) => {
        let at = c._at;
        if (at == null) {
          if (c.atWord && (c.atWord in timed)) at = l.start + Math.max(0, timed[c.atWord] - 0.08);
          else if (c.offset != null) at = l.start + c.offset;
          else at = l.start + 0.2 + ci * 2.2;
        }
        const until = Math.min(l.end, c.hold ? at + c.hold : l.end);
        CARDS.push({ at, until, tag: c.tag || "", title: c.title || "", sub: c.sub || "" });
      });
    });

    // 为每条有效字幕与卡片加落位检查点
    SUBS.forEach((s) => {
      if (s.end - s.start >= 0.35) D.settle(Math.min(s.end - 0.08, s.start + 0.25));
    });
    CARDS.forEach((c) => {
      if (c.until - c.at >= 0.9) D.settle(Math.min(c.until - 0.08, c.at + 0.78));
    });

    const cleanBrackets = (s) => (s || "").replace(/[\[\]]/g, "");
    window.__voice = FULL_AUDIO
      ? [{ file: NAR.fullAudio, start: NAR.audioOffset || 0 }]
      : LINES.map((l) => ({ file: l.file || `assets/voice/${l.id}.mp3`, start: l.start }));
    window.__subs = SUBS.map((s) => ({ start: s.start, end: s.end, zh: cleanBrackets(s.zh), en: cleanBrackets(s.en) }));
    window.__overlaps = FULL_AUDIO
      ? LINES.map(() => 0)
      : LINES.map((l, i) => (i < LINES.length - 1 ? +(l.start + l.dur - LINES[i + 1].start).toFixed(2) : 0));
    window.__hostLayout = hostBox;

    const subEl = document.getElementById("sub"), subZh = document.getElementById("subZh"), subEn = document.getElementById("subEn");
    const scard = document.getElementById("scard"), st = document.getElementById("st"), sw = document.getElementById("sw"), sm = document.getElementById("sm");
    let subCur = -1, cardCur = -1;
    const renderRich = (str) => str.split(/(\[[^\]]+\])/).map((seg) => seg.startsWith("[") ? `<span class="hi">${seg.slice(1, -1)}</span>` : seg.replace(/&/g, "&amp;").replace(/</g, "&lt;")).join("");

    function drawSubs(T) {
      const i = SUBS.findIndex((s) => T >= s.start - 0.12 && T < s.end + 0.2);
      if (i < 0) {
        subEl.style.opacity = 0;
      } else {
        const s = SUBS[i];
        if (i !== subCur) {
          subZh.innerHTML = renderRich(s.zh);
          if (s.en) { subEn.style.display = "block"; subEn.innerHTML = renderRich(s.en); }
          else { subEn.style.display = "none"; subEn.textContent = ""; }
          subCur = i;
        }
        const inK = E.outCubic(P(T, s.start - 0.12, s.start + 0.12));
        const out = E.inCubic(P(T, s.end, s.end + 0.2));
        subEl.style.opacity = inK * (1 - out);
        subEl.style.transform = `translateX(-50%) translateY(${(1 - inK) * 18 + out * 14}px)`;
      }

      const ci = CARDS.findLastIndex((c) => T >= c.at && T < c.until + 0.2);
      if (ci < 0) { scard.style.opacity = 0; return; }
      const c = CARDS[ci];
      if (ci !== cardCur) {
        if (c.tag) { st.style.display = "block"; st.textContent = c.tag; } else { st.style.display = "none"; st.textContent = ""; }
        sw.textContent = c.title;
        if (c.sub) { sm.style.display = "block"; sm.textContent = c.sub; } else { sm.style.display = "none"; sm.textContent = ""; }
        cardCur = ci;
      }
      const v = spring(T - c.at, 2.8, 0.5), o = E.inCubic(P(T, c.until, c.until + 0.2));
      scard.style.opacity = clamp((T - c.at) * 8) * (1 - o);
      scard.style.transform = `scale(${0.6 + 0.4 * v}) rotate(${(1 - v) * 5}deg)`;
    }

    // ---------- 语音包络 & 可选主讲人头像绘制 ----------
    const ENV_FPS = NAR.envFps || 30;
    function voiceLevelAt(T) {
      if (FULL_AUDIO) {
        const rel = T - (NAR.audioOffset || 0);
        if (rel < 0) return 0;
        if (Array.isArray(NAR.fullEnv) && NAR.fullEnv.length) {
          const idx = Math.round(rel * ENV_FPS);
          return idx >= 0 && idx < NAR.fullEnv.length ? NAR.fullEnv[idx] : 0;
        }
      }
      const line = LINES.find((l) => T >= l.start && T <= l.start + l.dur);
      if (!line) return 0;
      if (Array.isArray(line.env) && line.env.length) {
        const idx = Math.round((T - line.start) * ENV_FPS);
        return idx >= 0 && idx < line.env.length ? line.env[idx] : 0;
      }
      return 0.55;
    }

    function drawHost(T, tStory) {
      if (!HOST || !hostBox) return;
      if (hostBox.mode === "video" && hostBox.shape === "cutout" && !HOST.showPoster) {
        hostCv.style.display = "none"; return;
      }
      if (!hostImgs.main) { hostCv.style.display = "none"; return; }
      const endOut = END && tStory >= END.irisEnd - 0.15 ? clamp((tStory - (END.irisEnd - 0.15)) / 0.15) : 0;
      const inAt = HOST.inAt ?? 0.18;
      if (T < inAt || endOut >= 1) { hostCv.style.display = "none"; return; }
      if (Array.isArray(HOST.ranges) && !HOST.ranges.some(([a, b]) => T >= a && T <= b)) {
        hostCv.style.display = "none"; return;
      }
      hostCv.style.display = "block";
      const Wc = hostBox.width, Hc = hostBox.height;
      hostCtx.clearRect(0, 0, Wc, Hc);

      const enter = spring(T - inAt, 2.2, 0.58);
      const sc = enter * (1 - 0.25 * endOut);
      const alpha = clamp((T - inAt) * 6) * (1 - endOut);
      const lvl = hostBox.mode === "avatar" ? voiceLevelAt(T) : 0;
      const open = lvl * (0.45 + 0.55 * Math.abs(Math.sin(T * Math.PI * 5.2)));

      hostCtx.save();
      hostCtx.globalAlpha = alpha;
      if (hostBox.frame === "bust") {
        const im = (hostImgs.talk && open > 0.18) ? hostImgs.talk : hostImgs.main;
        const ar = im.naturalWidth / im.naturalHeight;
        const dh = Math.min(Hc, Wc / ar) * 0.96, dw = dh * ar;
        const nod = open * 0.025;
        hostCtx.translate(Wc / 2, Hc);
        hostCtx.scale(sc * (1 + nod * 0.7), sc * (1 - nod * 0.5));
        hostCtx.drawImage(im, -dw / 2, -dh - open * 5, dw, dh);
        hostCtx.restore();
        return;
      }

      const r = Wc / 2 - 4;
      hostCtx.translate(Wc / 2, Hc / 2);
      hostCtx.scale(sc, sc);
      hostCtx.save();
      hostCtx.beginPath();
      hostCtx.arc(0, 0, r, 0, Math.PI * 2);
      hostCtx.clip();
      hostCtx.fillStyle = HOST.bg || "#E9E4F5";
      hostCtx.fillRect(-r, -r, 2 * r, 2 * r);

      const im = (hostImgs.talk && open > 0.18) ? hostImgs.talk : hostImgs.main;
      const scale = Math.max((2 * r) / im.naturalWidth, (2 * r) / im.naturalHeight);
      const dw = im.naturalWidth * scale, dh = im.naturalHeight * scale;
      const dx = -dw / 2, dy = -dh / 2 - (im.naturalHeight > im.naturalWidth ? (dh - 2 * r) * 0.18 : 0);
      if (!hostImgs.talk && !HOST.mouth && open > 0.05) {
        hostCtx.save();
        hostCtx.translate(0, -open * 3);
        hostCtx.scale(1 + open * 0.03, 1 + open * 0.03);
        hostCtx.drawImage(im, dx, dy, dw, dh);
        hostCtx.restore();
      } else {
        hostCtx.drawImage(im, dx, dy, dw, dh);
      }

      if (HOST.mouth && open > 0.05 && !hostImgs.talk) {
        const mx = dx + HOST.mouth.x * dw, my = dy + HOST.mouth.y * dh;
        const ms = (HOST.mouth.s ?? 0.75) * (r / 110);
        hostCtx.save();
        hostCtx.translate(mx, my);
        hostCtx.scale(ms, ms);
        hostCtx.fillStyle = "#FDEBE8"; hostCtx.beginPath(); hostCtx.ellipse(0, 0, 17, 7, 0, 0, Math.PI * 2); hostCtx.fill();
        hostCtx.fillStyle = "#8A3F4A"; hostCtx.beginPath(); hostCtx.ellipse(0, 2, 7 + 6 * open, 2 + 9 * open, 0, 0, Math.PI * 2); hostCtx.fill();
        hostCtx.save(); hostCtx.clip();
        hostCtx.fillStyle = "#E58C96"; hostCtx.beginPath(); hostCtx.ellipse(0, 4 + 9 * open, 6 + 4 * open, 3 + 4 * open, 0, 0, Math.PI * 2); hostCtx.fill();
        hostCtx.restore();
        hostCtx.restore();
      }
      hostCtx.restore();

      hostCtx.lineWidth = 3; hostCtx.strokeStyle = "#FFFFFF";
      hostCtx.beginPath(); hostCtx.arc(0, 0, r + 1.5, 0, Math.PI * 2); hostCtx.stroke();
      hostCtx.lineWidth = 5; hostCtx.strokeStyle = HOST.borderColor || INK;
      hostCtx.beginPath(); hostCtx.arc(0, 0, r - 2.5, 0, Math.PI * 2); hostCtx.stroke();
      hostCtx.restore();
    }

    D.settle(1.2);

    // ---------- 多种换场地转场（默认轮换，不单调） ----------
    const CX = W / 2, CY = H / 2, RAD = Math.ceil(Math.hypot(W, H) / 2) + 400;
    const defaultTrans = cfg.transition || "auto";
    const wipeCues = cfg.wipeCues ?? [];
    LOCS.slice(1).forEach((loc, idx) => {
      const kind = loc.transition || (defaultTrans === "auto" ? TRANS_POOL[idx % TRANS_POOL.length] : defaultTrans);
      loc._trans = kind;
      if (kind !== "cut") wipeCues.forEach(([dt, s, g]) => C(loc.start + dt, s, g));
    });

    function transClip(kind, k) {
      if (k >= 1 || kind === "cut") return "none";
      if (kind === "wipe") return `inset(0 ${((1 - k) * 100).toFixed(3)}% 0 0)`;
      if (kind === "up") return `inset(${((1 - k) * 100).toFixed(3)}% 0 0 0)`;
      if (kind === "curtain") { const m = ((1 - k) * 50).toFixed(3); return `inset(0 ${m}% 0 ${m}%)`; }
      if (kind === "diagonal") {
        const sl = W * 0.28, xT = lerp(0, W + sl, k), xB = lerp(-sl, W, k);
        return `polygon(0px 0px, ${xT.toFixed(1)}px 0px, ${xB.toFixed(1)}px ${H}px, 0px ${H}px)`;
      }
      if (kind === "iris") {
        const cy = H * 0.46, r = k * Math.hypot(W, H) * 0.68, pts = [];
        for (let i = 0; i < 48; i++) {
          const a = (i / 48) * Math.PI * 2;
          pts.push(`${(CX + Math.cos(a) * r).toFixed(1)}px ${(cy + Math.sin(a) * r).toFixed(1)}px`);
        }
        return `polygon(${pts.join(",")})`;
      }
      // clock
      const a1 = -Math.PI / 2 + k * Math.PI * 2, pts = [`${CX}px ${CY}px`];
      const steps = Math.max(2, Math.ceil(k * 48));
      for (let i = 0; i <= steps; i++) {
        const a = -Math.PI / 2 + (a1 + Math.PI / 2) * (i / steps);
        pts.push(`${(CX + Math.cos(a) * RAD).toFixed(1)}px ${(CY + Math.sin(a) * RAD).toFixed(1)}px`);
      }
      return `polygon(${pts.join(",")})`;
    }

    function drawTransOver(kind, k) {
      if (k <= 0 || k >= 1 || kind === "cut") return;
      if (kind === "wipe") {
        const x = k * W;
        el(over, "line", { x1: x, y1: 0, x2: x, y2: H, stroke: INK, "stroke-width": 14 });
        el(over, "line", { x1: x - 9, y1: 0, x2: x - 9, y2: H, stroke: GOLD, "stroke-width": 5 });
      } else if (kind === "up") {
        const y = (1 - k) * H;
        el(over, "line", { x1: 0, y1: y, x2: W, y2: y, stroke: INK, "stroke-width": 14 });
        el(over, "line", { x1: 0, y1: y + 9, x2: W, y2: y + 9, stroke: GOLD, "stroke-width": 5 });
      } else if (kind === "curtain") {
        const x1 = W * (0.5 - 0.5 * k), x2 = W * (0.5 + 0.5 * k);
        el(over, "line", { x1, y1: 0, x2: x1, y2: H, stroke: INK, "stroke-width": 10 });
        el(over, "line", { x1: x2, y1: 0, x2: x2, y2: H, stroke: INK, "stroke-width": 10 });
      } else if (kind === "diagonal") {
        const sl = W * 0.28, xT = lerp(0, W + sl, k), xB = lerp(-sl, W, k);
        el(over, "line", { x1: xT, y1: 0, x2: xB, y2: H, stroke: INK, "stroke-width": 16 });
        el(over, "line", { x1: xT - 12, y1: 0, x2: xB - 12, y2: H, stroke: GOLD, "stroke-width": 5 });
      } else if (kind === "iris") {
        const cy = H * 0.46, r = k * Math.hypot(W, H) * 0.68;
        el(over, "circle", { cx: CX, cy, r, fill: "none", stroke: INK, "stroke-width": 12 });
      } else {
        const a = -Math.PI / 2 + k * Math.PI * 2, L2 = RAD - 200;
        const tipx = CX + Math.cos(a) * L2, tipy = CY + Math.sin(a) * L2, nx = -Math.sin(a), ny = Math.cos(a);
        el(over, "path", { d: `M${CX + nx * 16} ${CY + ny * 16} L${tipx + nx * 3} ${tipy + ny * 3} L${tipx - nx * 3} ${tipy - ny * 3} L${CX - nx * 16} ${CY - ny * 16} Z`, fill: INK });
        el(over, "circle", { cx: CX, cy: CY, r: 30, fill: GOLD, stroke: INK, "stroke-width": 6 });
      }
    }

    // ---------- 片尾：主线物件形状的光圈收拢，然后出片尾字 ----------
    const END = cfg.end || null;
    let irisFocus = [W / 2, H / 2];
    const setIrisFocus = (x, y) => { irisFocus = [x, y]; };
    const movePath = (d, x, y, s) => d.replace(/(-?\d+\.?\d*) (-?\d+\.?\d*)/g, (_, a, b) => `${x + a * s} ${y + b * s}`);
    function drawIris(t) {
      if (!END || t < END.irisStart) return;
      const t0 = END.irisStart, t1 = END.irisEnd, big = 22 * Math.max(W, H) / 1920; let s;
      if (t < t0 + 0.8) s = lerp(big, 1.9, E.outQuart(P(t, t0, t0 + 0.8)));
      else if (t < t1 - 0.3) s = 1.9 + Math.sin((t - t0 - 0.8) * 5) * 0.04;
      else s = lerp(1.9, 0, E.inBack(P(t, t1 - 0.3, t1), 1.6));
      const path = END.path || "M-100 0 C-100 -55 -55 -100 0 -100 C55 -100 100 -55 100 0 C100 55 55 100 0 100 C-55 100 -100 55 -100 0 Z";
      el(el(over, "g", {}), "path", { d: `M-10 -10 H${W + 10} V${H + 10} H-10 Z ${movePath(path, irisFocus[0], irisFocus[1], s)}`, fill: INK, "fill-rule": "evenodd" });
    }
    const endEl = document.getElementById("end"), endT = document.getElementById("endt");
    if (END) {
      const txt = END.text || "完";
      endT.textContent = txt;
      if (txt.length > 2) endT.style.fontSize = (tall ? 124 : 168) + "px";
    }

    // ---------- 每帧 ----------
    SV.start = (draw) => {
      for (const loc of LOCS) if (typeof draw[loc.id] !== "function") throw new Error(`场地 ${loc.id} 没有绘制函数`);
      D.onFrame((t) => {
        over.innerHTML = "";
        for (const loc of LOCS) {
          const o = L[loc.id];
          const durW = loc.wipe ?? WIPE;
          const vis = t >= loc.start && t < loc.end + durW && (!END || t < END.irisEnd + 0.05);
          o.el.style.display = vis ? "block" : "none";
          if (!vis) continue;
          for (const k in o.spr) o.spr[k].style.display = "none";
          o.fx.innerHTML = "";
          const wk = loc.start > 0 ? (durW <= 0 || loc._trans === "cut" ? 1 : P(t, loc.start, loc.start + durW)) : 1;
          const easedK = E.inOutSine(wk);
          o.el.style.clipPath = transClip(loc._trans, easedK);
          o.el.style.zIndex = LOCS.indexOf(loc);
          draw[loc.id](t);
          if (loc.start > 0 && wk < 1) drawTransOver(loc._trans, easedK);
        }
        drawSubs(VB);
        drawHost(VB, t);
        drawIris(t);
        const showEnd = END && t >= END.irisEnd;
        endEl.style.display = showEnd ? "flex" : "none";
        if (showEnd) {
          const v = spring(t - END.textAt, 2.4, 0.5);
          endT.style.transform = `scale(${0.2 + 0.8 * v}) rotate(${(1 - v) * -12}deg)`;
          endT.style.opacity = clamp((t - END.textAt) * 8);
        }
      });
    };

    Object.assign(window, { W, H, INK, CREAM, GOLD, ACCENT, DUST, E, P, lerp, spring, clamp, hash, D, C, L, AR, over, TITLE, FACT, GROUND,
      put, SZ, gAt, squash, el, puff, star, twinkle, speed, zap, camera, shake, makeInset, setIrisFocus, videoOf, storyOf, DUR, VDUR });
  };
})();
