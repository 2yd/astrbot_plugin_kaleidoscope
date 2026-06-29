#!/usr/bin/env python3
"""
万花筒效果本地测试脚本

用法:
    python test_kaleidoscope.py <输入图片路径> [输出路径]

示例:
    python test_kaleidoscope.py ~/Desktop/test.jpg
    python test_kaleidoscope.py ~/Desktop/test.gif output.gif
    python test_kaleidoscope.py cat.png --branches 12 --layers 6

依赖: pip install Pillow
"""

import argparse
import math
import sys
from pathlib import Path
from PIL import Image, ImageSequence, ImageFile


# ========================== 算法参数（可调） ==========================

CANVAS_SIZE = 600
BRANCH_COUNT = 8          # 分支数
LAYER_COUNT = 5            # 每分支层数
BASE_SIZE = 180            # 基础元素长边

# 每层距离圆心的距离
LAYER_DISTANCES = [50, 85, 135, 185, 240]

# 每层缩放比例（最内层略微放大）
LAYER_SCALES = [0.22, 0.35, 0.58, 0.85, 1.0]


# ========================== 静态图处理 ==========================

def to_rgba(image: Image.Image) -> Image.Image:
    """统一转 RGBA，保留透明度"""
    if image.mode == "RGBA":
        return image
    if image.mode in ("P", "LA"):
        return image.convert("RGBA")
    return image.convert("RGBA")  # RGB → RGBA（alpha 全 255）


def resize_base_element(image: Image.Image) -> Image.Image:
    """缩放到基础元素尺寸（长边 = BASE_SIZE）"""
    w, h = image.size
    max_dim = max(w, h)
    if max_dim <= 2:
        return image
    ratio = BASE_SIZE / max_dim
    return image.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)


def apply_kaleidoscope(image: Image.Image) -> Image.Image:
    """
    放射状分支万花筒核心算法
    8 分支 × 5 层 = 40 个元素，缩放+距离从内到外递增
    """
    # 准备基础元素
    base = resize_base_element(image)
    bw, bh = base.size

    # 创建画布（RGBA，最后可转 RGB）
    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (255, 255, 255, 255))
    cx = cy = CANVAS_SIZE / 2

    # 绘制所有分支
    for branch_idx in range(BRANCH_COUNT):
        angle_deg = branch_idx * (360 / BRANCH_COUNT)
        angle_rad = math.radians(angle_deg)

        for layer_idx in range(LAYER_COUNT):
            distance = LAYER_DISTANCES[layer_idx]
            scale = LAYER_SCALES[layer_idx]

            scaled_w = int(bw * scale)
            scaled_h = int(bh * scale)
            if scaled_w < 1 or scaled_h < 1:
                continue

            scaled = base.resize((scaled_w, scaled_h), Image.LANCZOS)

            # 旋转：顶部背对圆心（朝外）
            # angle_deg=0(右)→rotation=-90(顺时针90°,顶朝右) ✓
            # angle_deg=45(右上)→rotation=-45(顺时针45°) ✓
            # angle_deg=90(上)→rotation=0(不转) ✓
            # 用 RGBA 透明底色 expand=True，粘贴时 alpha 遮罩防止覆盖相邻元素
            rotation = angle_deg - 90.0
            scaled_rgba = scaled.convert("RGBA")
            rotated = scaled_rgba.rotate(
                rotation, resample=Image.BICUBIC, expand=True,
                fillcolor=(0, 0, 0, 0),
            )

            # 放置到分支上的位置
            pos_x = cx + distance * math.cos(angle_rad) - rotated.width / 2
            pos_y = cy - distance * math.sin(angle_rad) - rotated.height / 2
            canvas.paste(rotated, (int(pos_x), int(pos_y)), mask=rotated.split()[3])

    return canvas


# ========================== GIF 动图处理 ==========================

def process_gif(input_path: str, output_path: str):
    """逐帧处理 GIF"""
    ImageFile.LOAD_TRUNCATED_IMAGES = True

    try:
        frames = []
        durations = []

        with Image.open(input_path) as gif:
            for frame in ImageSequence.Iterator(gif):
                durations.append(frame.info.get("duration", 100))

                frame_copy = frame.copy()
                frame_copy = to_rgba(frame_copy)

                kaleido = apply_kaleidoscope(frame_copy)
                frames.append(kaleido)

        if not frames:
            print("错误: GIF 无帧数据", file=sys.stderr)
            return

        # 统一帧尺寸 + 量化
        target = frames[0].size
        normalized = []
        for f in frames:
            if f.size != target:
                f = f.resize(target, Image.LANCZOS)
            if f.mode != "RGB":
                f = f.convert("RGB")
            normalized.append(f)

        gif_frames = [f.quantize(colors=226) for f in normalized]

        while len(durations) < len(gif_frames):
            durations.append(100)
        durations = durations[: len(gif_frames)]

        gif_frames[0].save(
            output_path,
            save_all=True,
            append_images=gif_frames[1:],
            duration=durations,
            loop=0,
            disposal=2,
        )
        print(f"✅ GIF 处理完成 ({len(gif_frames)} 帧) → {output_path}")

    finally:
        ImageFile.LOAD_TRUNCATED_IMAGES = False


# ========================== 主入口 ==========================

def main():
    parser = argparse.ArgumentParser(description="万花筒效果本地测试工具")
    parser.add_argument("input", help="输入图片路径 (png/jpg/gif/webp/bmp)")
    parser.add_argument("output", nargs="?", help="输出路径 (默认: kaleido_output.png)")
    parser.add_argument("--branches", type=int, default=8, help="分支数 (默认: 8)")
    parser.add_argument("--layers", type=int, default=5, help="每分支层数 (默认: 5)")
    parser.add_argument("--canvas", type=int, default=600, help="画布尺寸 (默认: 600)")
    parser.add_argument("--base-size", type=int, default=180, help="基础元素长边 (默认: 180)")
    args = parser.parse_args()

    # 覆盖全局参数
    global CANVAS_SIZE, BRANCH_COUNT, LAYER_COUNT, BASE_SIZE
    global LAYER_DISTANCES, LAYER_SCALES
    CANVAS_SIZE = args.canvas
    BRANCH_COUNT = args.branches
    LAYER_COUNT = args.layers
    BASE_SIZE = args.base_size

    # 只有显式改变了分支数或层数时才动态重算距离/缩放
    # 否则使用文件顶部微调好的硬编码值
    if args.branches != 8 or args.layers != 5:
        max_dist = int(CANVAS_SIZE * 0.48)
        LAYER_DISTANCES = [
            int(max_dist * (i + 1) / LAYER_COUNT) for i in range(LAYER_COUNT)
        ]
        LAYER_SCALES = [
            0.15 + (0.75 * (i + 1) / LAYER_COUNT) for i in range(LAYER_COUNT)
        ]
        print("⚠️  使用动态参数（非默认分支/层数）")

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误: 文件不存在: {input_path}", file=sys.stderr)
        sys.exit(1)

    # 输出路径
    if args.output:
        output_path = args.output
    else:
        suffix = input_path.suffix or ".png"
        output_path = f"kaleido_output{suffix}"

    ext = input_path.suffix.lower()
    print(f"📷 输入: {input_path} ({ext})")
    print(f"🎨 参数: {BRANCH_COUNT}分支 × {LAYER_COUNT}层, "
          f"画布{CANVAS_SIZE}×{CANVAS_SIZE}, 基础元素{BASE_SIZE}px")
    print(f"📐 距离: {LAYER_DISTANCES}")
    print(f"📐 缩放: {[f'{s:.2f}' for s in LAYER_SCALES]}")
    print(f"💾 输出: {output_path}")
    print("---")

    if ext == ".gif":
        process_gif(str(input_path), output_path)
    else:
        with Image.open(input_path) as img:
            print(f"   原图: {img.size}, mode={img.mode}")
            img = to_rgba(img)  # 保持 RGBA，不用白底合成，消除白边
            result = apply_kaleidoscope(img)

        output_ext = Path(output_path).suffix.lower()
        # JPG 不支持透明，需转为 RGB
        if output_ext in (".jpg", ".jpeg"):
            result = result.convert("RGB")
            result.save(output_path, quality=85, optimize=True)
        elif output_ext == ".png":
            result.save(output_path, optimize=True)
        elif output_ext == ".webp":
            result.save(output_path, quality=85, method=6)
        else:
            result.save(output_path, quality=85, optimize=True)

        print(f"✅ 处理完成 → {output_path}")


if __name__ == "__main__":
    main()
