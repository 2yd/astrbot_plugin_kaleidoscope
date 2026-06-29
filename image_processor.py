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
    CANVAS_SIZE = 600  # 600 × 600

    # 分支数量
    BRANCH_COUNT = 8  # 360°/8 = 45° 均分

    # 每分支元素层数
    LAYER_COUNT = 5

    # 每层距离圆心的距离（像素）
    LAYER_DISTANCES = [50, 85, 135, 185, 240]

    # 每层缩放比例（基础元素长边=180px）
    LAYER_SCALES = [0.22, 0.35, 0.58, 0.85, 1.0]

    # 基础元素长边尺寸（像素）
    BASE_SIZE = 180

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
                if mode == "reverse":
                    return await KaleidoscopeProcessor._process_reverse_gif(
                        input_path, output_path, config
                    )
                return await KaleidoscopeProcessor._process_gif(
                    input_path, output_path, mode, config
                )
            else:
                if mode == "reverse":
                    # 静态图倒放 = 原图直接复制
                    import shutil
                    shutil.copy(input_path, output_path)
                    return True, "倒放完成"
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
        """处理 GIF 动图：分批提交 executor（每批10帧），批次间 yield"""
        try:
            loop = asyncio.get_running_loop()
            quality = config.output_quality if config else 85
            max_frames = config.max_gif_frames if config else 200

            # ---- 阶段 1：主线程收集帧 ----
            frame_data = []   # [(rgba_image, duration), ...]
            has_transparency = False
            frame_count = 0

            # 兼容被截断的 GIF（与测试脚本保持一致）
            original_load_truncated = ImageFile.LOAD_TRUNCATED_IMAGES
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            try:
                with Image.open(input_path) as gif:
                    has_transparency = "transparency" in gif.info
                    for raw_frame in ImageSequence.Iterator(gif):
                        frame_count += 1
                        if frame_count > max_frames:
                            return False, f"GIF 帧数过多（{frame_count} > {max_frames}）"
                        dur = raw_frame.info.get("duration", 100)
                        has_transparency = has_transparency or ("transparency" in raw_frame.info)
                        f = raw_frame.copy()
                        f = KaleidoscopeProcessor._to_rgba(f)
                        frame_data.append((f, dur))
            finally:
                ImageFile.LOAD_TRUNCATED_IMAGES = original_load_truncated

            if frame_count > 100:
                logger.warning(f"处理大型 GIF: {frame_count} 帧")
            if not frame_data:
                return False, "GIF 没有帧数据"

            # ---- 阶段 2：分批 executor（每批 10 帧） ----
            BATCH = 10

            def process_batch(batch_frames):
                return [KaleidoscopeProcessor._apply_kaleidoscope(bf) for bf in batch_frames]

            processed = []
            durations = []
            for i in range(0, len(frame_data), BATCH):
                batch = frame_data[i : i + BATCH]
                batch_frames = [bf[0] for bf in batch]
                results = await loop.run_in_executor(None, process_batch, batch_frames)
                processed.extend(results)
                durations.extend(bf[1] for bf in batch)
                await asyncio.sleep(0)  # 批次间 yield

            # ---- 阶段 3：合成保存 ----
            def assemble_gif(frames, durs, has_transp, q):
                target = frames[0].size
                normalized = []
                for f in frames:
                    if f.size != target:
                        f = f.resize(target, Image.LANCZOS)
                    if f.mode != "RGB":
                        f = f.convert("RGB")
                    normalized.append(f)

                colors = max(64, min(255, int(32 + 96 * q / 100)))
                gf = [f.quantize(colors=colors) for f in normalized]
                while len(durs) < len(gf):
                    durs.append(100)
                durs = durs[: len(gf)]
                kw = {"save_all": True, "append_images": gf[1:] if len(gf) > 1 else [],
                      "duration": durs, "loop": 0, "disposal": 2}
                if has_transp:
                    kw["transparency"] = 0
                gf[0].save(output_path, **kw)

            await loop.run_in_executor(
                None, assemble_gif, processed, durations, has_transparency, quality
            )

            return True, "万花筒 GIF 处理成功"

        except Exception as e:
            logger.error(f"GIF 处理失败: {e}", exc_info=True)
            return False, f"GIF 处理失败: {str(e)}"

    # ======================== 倒放 ========================

    @staticmethod
    async def _process_reverse_gif(
        input_path: str, output_path: str, config: Optional[PluginConfig] = None
    ) -> Tuple[bool, str]:
        """GIF 倒放：反转帧顺序"""
        try:
            loop = asyncio.get_running_loop()
            max_frames = config.max_gif_frames if config else 200

            def reverse_gif():
                with Image.open(input_path) as gif:
                    frames = []
                    durations = []
                    for raw_frame in ImageSequence.Iterator(gif):
                        if len(frames) >= max_frames:
                            break
                        durations.append(raw_frame.info.get("duration", 100))
                        f = raw_frame.copy()
                        f = KaleidoscopeProcessor._to_rgba(f)
                        frames.append(f)

                if not frames:
                    return False

                # 反转帧顺序
                frames.reverse()
                durations.reverse()

                # 保持原质量，只转 P 模式（GIF 要求）
                gif_frames = [f.convert("P", palette=Image.ADAPTIVE) for f in frames]
                save_kwargs = {
                    "save_all": True,
                    "append_images": gif_frames[1:],
                    "duration": durations,
                    "loop": 0,
                    "disposal": 2,
                }
                gif_frames[0].save(output_path, **save_kwargs)
                return True

            success = await loop.run_in_executor(None, reverse_gif)
            return (True, "倒放完成") if success else (False, "GIF 处理失败")

        except Exception as e:
            logger.error(f"GIF 倒放失败: {e}", exc_info=True)
            return False, f"倒放失败: {str(e)}"

    @staticmethod
    def get_mode_description(mode: str) -> str:
        descriptions = {
            "kaleidoscope": "万花筒效果（8分支放射对称 + 缩放透视）",
            "reverse": "倒放效果",
        }
        return descriptions.get(mode, "未知模式")
