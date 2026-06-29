"""
万花筒图像处理模块

放射状分支万花筒算法：
- 以纯白画布(1000x1000)正中心为圆心
- 向外延伸 8 个分支（45°均分）
- 每分支放置 5 个基础元素副本
- 越靠近中心缩放越小，越靠边缘缩放越大
- 每个元素旋转使其顶部背对圆心、朝向外侧

支持：静态图 + GIF 动图
"""

import asyncio
import math
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image, ImageSequence, ImageFile

from .config import PluginConfig
from astrbot.api import logger


class KaleidoscopeProcessor:
    """万花筒图像处理器"""

    # 画布尺寸
    CANVAS_SIZE = 1000  # 1000 × 1000

    # 分支数量
    BRANCH_COUNT = 8  # 360°/8 = 45° 均分

    # 每分支元素层数
    LAYER_COUNT = 5

    # 每层距离圆心的距离（像素）
    # 从内到外递增，层间更紧凑
    LAYER_DISTANCES = [80, 130, 210, 300, 400]

    # 每层缩放比例（基础元素长边=300px）
    # 从内到外递增，全线放大，产生强烈透视感
    LAYER_SCALES = [0.18, 0.35, 0.58, 0.85, 1.0]

    # 基础元素长边尺寸（像素）
    BASE_SIZE = 300

    @staticmethod
    async def process_image(
        input_path: str,
        output_path: str,
        mode: str,
        config: Optional[PluginConfig] = None,
    ) -> Tuple[bool, str]:
        """
        图像处理主函数（静态图 + GIF）

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            mode: 处理模式
            config: 配置

        Returns:
            (成功, 描述)
        """
        try:
            if not Path(input_path).exists():
                return False, f"输入文件不存在: {input_path}"

            loop = asyncio.get_running_loop()

            # 判断是否为 GIF
            ext = Path(input_path).suffix.lower()
            is_gif = ext == ".gif"

            if is_gif:
                # GIF 处理：逐帧万花筒 + 合成为动图
                return await KaleidoscopeProcessor._process_gif(
                    input_path, output_path, mode, config
                )
            else:
                # 静态图处理（保持 RGBA，不烘焙白底，消除透明图白边）
                def process_in_thread():
                    with Image.open(input_path) as img:
                        img = KaleidoscopeProcessor._to_rgba(img)
                        result = KaleidoscopeProcessor._apply_kaleidoscope(img)
                        KaleidoscopeProcessor._save_result(result, output_path, config)
                        return True

                await loop.run_in_executor(None, process_in_thread)
                return True, "万花筒处理成功"

        except Exception as e:
            logger.error(f"万花筒处理失败: {e}", exc_info=True)
            return False, f"图像处理失败: {str(e)}"

    # ======================== 静态图处理 ========================

    @staticmethod
    def _to_rgba(img: Image.Image) -> Image.Image:
        """统一转为 RGBA，保留透明度（不烘焙白底）"""
        if img.mode == "RGBA":
            return img
        return img.convert("RGBA")

    @staticmethod
    def _apply_kaleidoscope(image: Image.Image) -> Image.Image:
        """
        放射状分支万花筒核心算法

        1. 将原图缩放到标准基础元素尺寸（长边=200px）
        2. 在 1000×1000 白色画布上：
           - 8 个分支，45° 均分
           - 每分支 5 层元素
           - 缩放和距离从内到外递增
           - 每个元素旋转使顶部背对圆心
        """
        # ---- 1. 准备基础元素 ----
        base = KaleidoscopeProcessor._resize_base_element(image)
        bw, bh = base.size

        # ---- 2. 创建画布 ----
        canvas_size = KaleidoscopeProcessor.CANVAS_SIZE
        canvas = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 255))
        cx, cy = canvas_size / 2, canvas_size / 2  # 中心坐标

        # ---- 3. 绘制所有分支 ----
        for branch_idx in range(KaleidoscopeProcessor.BRANCH_COUNT):
            angle_deg = branch_idx * (360 / KaleidoscopeProcessor.BRANCH_COUNT)
            angle_rad = math.radians(angle_deg)

            for layer_idx in range(KaleidoscopeProcessor.LAYER_COUNT):
                distance = KaleidoscopeProcessor.LAYER_DISTANCES[layer_idx]
                scale = KaleidoscopeProcessor.LAYER_SCALES[layer_idx]

                # 缩放基础元素
                scaled_w = int(bw * scale)
                scaled_h = int(bh * scale)
                if scaled_w < 1 or scaled_h < 1:
                    continue

                scaled = base.resize((scaled_w, scaled_h), Image.LANCZOS)

                # 旋转：保证图片"顶部"背对圆心、朝向外侧
                # angle_deg=0°(右)→rotation=-90°(顺时针90°,顶朝右) ✓
                # angle_deg=45°(右上)→rotation=-45°(顺时针45°) ✓
                # angle_deg=90°(上)→rotation=0°(不转) ✓
                # 用 RGBA 透明底色 expand=True，粘贴时 alpha 遮罩防止覆盖相邻元素
                rotation = angle_deg - 90.0

                scaled_rgba = scaled.convert("RGBA")
                rotated = scaled_rgba.rotate(
                    rotation, resample=Image.BICUBIC, expand=True,
                    fillcolor=(0, 0, 0, 0),
                )

                # 计算放置位置（元素中心定位到分支上的点）
                # canvas坐标: x右增, y下增
                # 方向向量: (cosθ, -sinθ)  —— y轴翻转
                pos_x = cx + distance * math.cos(angle_rad) - rotated.width / 2
                pos_y = cy - distance * math.sin(angle_rad) - rotated.height / 2

                # 粘贴到画布（alpha 通道做遮罩）
                canvas.paste(rotated, (int(pos_x), int(pos_y)), mask=rotated.split()[3])

        return canvas

    @staticmethod
    def _resize_base_element(image: Image.Image) -> Image.Image:
        """
        将图片缩放为标准基础元素尺寸（长边 = BASE_SIZE，保持宽高比）
        """
        w, h = image.size
        max_dim = max(w, h)
        if max_dim <= 2:
            return image

        ratio = KaleidoscopeProcessor.BASE_SIZE / max_dim
        new_w = max(1, int(w * ratio))
        new_h = max(1, int(h * ratio))
        return image.resize((new_w, new_h), Image.LANCZOS)

    @staticmethod
    def _save_result(
        img: Image.Image,
        output_path: str,
        config: Optional[PluginConfig] = None,
    ):
        """保存处理结果（JPG 需转 RGB，PNG 保留 RGBA）"""
        quality = config.output_quality if config else 85
        output_ext = Path(output_path).suffix.lower()

        if output_ext in (".jpg", ".jpeg"):
            if img.mode == "RGBA":
                img = img.convert("RGB")
            img.save(output_path, quality=quality, optimize=True)
        elif output_ext == ".png":
            img.save(output_path, optimize=True)
        elif output_ext == ".webp":
            img.save(output_path, quality=quality, method=6)
        else:
            if img.mode == "RGBA":
                img = img.convert("RGB")
            img.save(output_path, quality=quality, optimize=True)

    # ======================== GIF 动图处理 ========================

    @staticmethod
    async def _process_gif(
        input_path: str,
        output_path: str,
        mode: str,
        config: Optional[PluginConfig] = None,
    ) -> Tuple[bool, str]:
        """
        处理 GIF 动图：逐帧应用万花筒效果后合成

        参考 pic-mirror 的 GIF 处理流程
        """
        try:
            loop = asyncio.get_running_loop()

            def process_gif_in_thread():
                original_load = ImageFile.LOAD_TRUNCATED_IMAGES
                ImageFile.LOAD_TRUNCATED_IMAGES = True

                try:
                    frames = []
                    durations = []
                    has_transparency = False
                    max_frames = config.max_gif_frames if config else 200

                    with Image.open(input_path) as gif:
                        # 检测透明度
                        if "transparency" in gif.info:
                            has_transparency = True

                        frame_count = 0
                        for frame in ImageSequence.Iterator(gif):
                            frame_count += 1
                            if frame_count > max_frames:
                                return (None, f"GIF 帧数过多（{frame_count} > {max_frames}）")

                            # 记录帧时长
                            durations.append(frame.info.get("duration", 100))

                            # 检测帧透明度
                            if "transparency" in frame.info:
                                has_transparency = True

                            # 复制并转为 RGBA 处理（保持透明度，避免白边）
                            frame_copy = frame.copy()
                            frame_copy = KaleidoscopeProcessor._to_rgba(frame_copy)

                            # 应用万花筒
                            kaleido_frame = KaleidoscopeProcessor._apply_kaleidoscope(frame_copy)

                            frames.append(kaleido_frame)

                        if frame_count > 100:
                            logger.warning(f"处理大型 GIF: {frame_count} 帧")

                    if not frames:
                        return (None, "GIF 没有帧数据")

                    # 统一帧尺寸
                    target_size = frames[0].size
                    normalized = []
                    for f in frames:
                        if f.size != target_size:
                            f = f.resize(target_size, Image.LANCZOS)
                        if f.mode != "RGB":
                            f = f.convert("RGB")
                        normalized.append(f)

                    # 质量映射
                    quality = config.output_quality if config else 85
                    palette_colors = max(64, min(255, int(64 + (255 - 64) * quality / 100)))

                    # 量化帧（减色以缩小 GIF 体积）
                    gif_frames = []
                    for f in normalized:
                        if has_transparency:
                            p_frame = f.quantize(colors=palette_colors)
                        else:
                            p_frame = f.quantize(colors=palette_colors)
                        gif_frames.append(p_frame)

                    # 对齐 durations
                    while len(durations) < len(gif_frames):
                        durations.append(100)
                    durations = durations[: len(gif_frames)]

                    # 保存 GIF
                    save_kwargs = {
                        "save_all": True,
                        "append_images": gif_frames[1:] if len(gif_frames) > 1 else [],
                        "duration": durations,
                        "loop": 0,
                        "disposal": 2,
                    }
                    if has_transparency:
                        save_kwargs["transparency"] = 0

                    gif_frames[0].save(output_path, **save_kwargs)
                    return (gif_frames, None)

                finally:
                    ImageFile.LOAD_TRUNCATED_IMAGES = original_load

            result = await loop.run_in_executor(None, process_gif_in_thread)

            if result[0] is None:
                return False, result[1]

            return True, "万花筒 GIF 处理成功"

        except Exception as e:
            logger.error(f"GIF 处理失败: {e}", exc_info=True)
            return False, f"GIF 处理失败: {str(e)}"

    @staticmethod
    def get_mode_description(mode: str) -> str:
        descriptions = {
            "kaleidoscope": "万花筒效果（8分支放射对称 + 缩放透视）",
        }
        return descriptions.get(mode, "未知模式")
