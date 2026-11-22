"""整理项目素材：支持两种来源——
1) 按 assets/urls.txt（每行：名字 网址）自动下载到 assets/raw/；
2) 也直接处理已放到 assets/raw/ 里的本地图片或 libtv_story.py 下载的 PNG/JPG。
命名规范：
- B*：背景图，按 page/aspect.txt（默认 16:9）居中裁切为 1920×1080 或 1080×1920 JPG → assets/bg/
- C*：角色/道具图 → assets/cut/（直接验证原生 Alpha 并裁边）
- H*：主讲人头像/半身像 → assets/host/（验证原生 Alpha 并裁边；导入旧绿幕素材时可显式传 --legacy-green）
用法：~/.venvs/vocab-story/bin/python fetch_assets.py 项目目录
依赖：numpy、Pillow、scipy（与 key.py 相同）"""
import pathlib, sys, urllib.request
import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from native_alpha import check_alpha
from key import key, MAXSIDE  # noqa: E402

root = pathlib.Path(sys.argv[1]).resolve()
raw, bg, cut, host = root / "assets/raw", root / "assets/bg", root / "assets/cut", root / "assets/host"
asp = (root / "page/aspect.txt").read_text().strip() if (root / "page/aspect.txt").exists() else "16:9"
SIZE = {"16:9": (1920, 1080), "9:16": (1080, 1920)}[asp]
for d in (raw, bg, cut, host):
    d.mkdir(parents=True, exist_ok=True)


def is_green_backdrop(im: Image.Image) -> bool:
    rgb = np.asarray(im.convert("RGB")).astype(np.float32)
    dom = rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2])
    h, w = dom.shape
    edges = np.concatenate([dom[0, :], dom[-1, :], dom[:, 0], dom[:, -1]])
    return float((edges > 45).mean()) > 0.35


def save_rgba_trimmed(im: Image.Image, out_path: pathlib.Path, max_side: int = MAXSIDE) -> None:
    rgba = im.convert("RGBA")
    bbox = rgba.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox:
        rgba = rgba.crop(bbox)
    s = max_side / max(rgba.size)
    if s < 1:
        rgba = rgba.resize((round(rgba.width * s), round(rgba.height * s)), Image.LANCZOS)
    rgba.save(out_path, optimize=True)
    print(f"{out_path.name}: {rgba.size} (原生透明裁边)")


urls_file = root / "assets/urls.txt"
if urls_file.exists():
    for line in urls_file.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        name, url = line.split()[:2]
        src = raw / f"{name}.png"
        if not src.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            src.write_bytes(urllib.request.urlopen(req, timeout=120).read())
            print("下载", name)

for src in sorted(raw.iterdir()):
    if not src.is_file() or src.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        continue
    name = src.stem
    if name.startswith("B"):
        dest = bg / f"{name}.jpg"
        if not dest.exists():
            ImageOps.fit(Image.open(src).convert("RGB"), SIZE, Image.LANCZOS).save(dest, quality=92)
            print(f"{dest.name}: {SIZE} (背景裁切)")
    elif name.startswith(("C", "H")):
        dest = (cut if name.startswith("C") else host) / f"{name}.png"
        with Image.open(src) as im:
            try:
                check_alpha(im, src.name)
            except ValueError:
                if "--legacy-green" in sys.argv[2:] and is_green_backdrop(im):
                    key(src, dest.parent)
                    continue
                raise
            save_rgba_trimmed(im, dest, max_side=MAXSIDE if name.startswith("C") else 1024)
