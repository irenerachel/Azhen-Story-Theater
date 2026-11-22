"""检查生成的 PNG 确实具有可用的透明背景；保留原始抗锯齿像素。"""
from PIL import Image


def check_alpha(im, name, trimmed=False):
    if im.mode not in ("RGBA", "LA") and "transparency" not in im.info:
        raise ValueError(f"{name} 缺少 Alpha，请以透明背景重新生成。")
    alpha = im.convert("RGBA").getchannel("A")
    counts = alpha.histogram()
    w, h = im.size
    if sum(counts[:16]) < w*h*0.01 or sum(counts[128:]) < w*h*0.005:
        raise ValueError(f"{name} 需要同时包含可见主体与透明留白，请检查生成结果。")
    if not trimmed and not any(alpha.getpixel(point) < 32 for point in [(0,0),(w-1,0),(0,h-1),(w-1,h-1)]):
        raise ValueError(f"{name} 画布四角均有内容，请检查透明背景与留白。")
