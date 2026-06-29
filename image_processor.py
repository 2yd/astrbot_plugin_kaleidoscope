"""
万花筒图像处理模块

将图像通过六边形对称翻转 + 色调偏移模拟万花筒视觉效果。
当前为简化实现，后续可扩展更多变体。
"""

import asyncio
import math
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image, ImageEnhance, ImageOps

from .config import PluginConfig
from astrbot.api import logger


class KaleidoscopeProcessor:
    """万花筒图像处理器"""

    @staticmethod
    async def process_image(
        input_path: str,
        output_path: str,
        mode: str,
        config: Optional[PluginConfig] = None,
    ) -> Tuple[bool, str]:
        """
        处理图像的主函数

        Args:
            input_path: 输入图像路径
            output_path: 输出图像路径
            mode: 万花筒模式
            config: 插件配置

        Returns:
            Tuple[bool, str]: (是否成功, 描述信息)
        """
        try:
            if not Path(input_path).exists():
                return False, f"输入文件不存在: {input_path}"

            loop = asyncio.get_running_loop()

            def process_in_thread():
                with Image.open(input_path) as img:
                    # 统一转RGB处理
                    if img.mode in ("RGBA", "LA", "P"):
                        if img.mode == "P":
                            img = img.convert("RGBA")
                        background = Image.new("RGB", img.size, (255, 255, 255))
                        if img.mode == "RGBA":
                            background.paste(img, mask=img.split()[3])
                        else:
                            background.paste(img)
                        img = background
                    elif img.mode != "RGB":
                        img = img.convert("RGB")

                    # 应用万花筒效果
                    if mode == "kaleidoscope":
                        result = KaleidoscopeProcessor._apply_kaleidoscope(img)
                    else:
                        result = img.copy()

                    # 保存
                    quality = config.output_quality if config else 85
                    output_ext = Path(output_path).suffix.lower()
                    if output_ext == ".png":
                        result.save(output_path, optimize=True)
                    elif output_ext == ".webp":
                        result.save(output_path, quality=quality, method=6)
                    else:
                        result.save(output_path, quality=quality, optimize=True)

                    return True

            await loop.run_in_executor(None, process_in_thread)
            return True, "万花筒处理成功"

        except Exception as e:
            logger.error(f"万花筒处理失败: {e}", exc_info=True)
            return False, f"图像处理失败: {str(e)}"

    @staticmethod
    def _apply_kaleidoscope(image: Image.Image) -> Image.Image:
        """
        应用万花筒效果

        核心思路：
        1. 将图像裁剪为正方形（取中心最大正方形）
        2. 分为6个等边三角形扇形（60度一个）
        3. 对每个扇形应用镜像翻转
        4. 叠加轻微色调偏移

        Args:
            image: PIL Image 对象 (RGB)

        Returns:
            处理后的 Image 对象
        """
        width, height = image.size

        # 1. 裁剪为正方形
        side = min(width, height)
        left = (width - side) // 2
        top = (height - side) // 2
        image = image.crop((left, top, left + side, top + side))

        # 2. 取上半部分作为基础扇形（60度三角形）
        result = Image.new("RGB", (side, side))

        # 计算中心点
        cx, cy = side // 2, side // 2
        radius = side // 2

        # 2a. 从原图中提取一个 60 度扇形区域
        # 创建一个扇形 mask
        mask = Image.new("L", (side, side), 0)

        # 用三角函数画出60度扇形（从 -30度 到 +30度，顶点朝上）
        import math
        for y in range(side):
            for x in range(side):
                dx = x - cx
                dy = y - cy
                dist = math.sqrt(dx * dx + dy * dy)
                if dist <= radius:
                    # 计算角度（从正上方顺时针），范围 [-180, 180]
                    angle = math.degrees(math.atan2(dx, -dy))
                    # 限定在 [-30, 30] 度（60度扇形）
                    if -30 <= angle <= 30:
                        mask.putpixel((x, y), 255)

        # 提取扇形区域
        sector = Image.new("RGB", (side, side))
        sector.paste(image, mask=mask)

        # 2b. 旋转扇形6次拼成完整的万花筒图案
        for i in range(6):
            angle = i * 60  # 每个扇形60度
            rotated = sector.rotate(angle, resample=Image.BICUBIC, center=(cx, cy))
            result = Image.composite(rotated, result, rotated.convert("L"))

        # 3. 轻微增强色彩饱和度
        enhancer = ImageEnhance.Color(result)
        result = enhancer.enhance(1.3)

        # 4. 增强对比度让万花筒效果更鲜明
        contrast_enhancer = ImageEnhance.Contrast(result)
        result = contrast_enhancer.enhance(1.15)

        return result

    @staticmethod
    def get_mode_description(mode: str) -> str:
        """获取处理模式的描述"""
        descriptions = {
            "kaleidoscope": "万花筒效果（六边形对称翻转 + 色调增强）",
        }
        return descriptions.get(mode, "未知模式")
