"""
万花筒图像处理插件主入口

用法：
- 发送一张图片并 @机器人 说「万花筒」，即可生成万花筒效果
- 直接发送 /万花筒 指令（消息中含图片）
"""

import asyncio

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.core.star.filter.event_message_type import EventMessageType
from astrbot.api.star import Context, Star
from astrbot.api import logger

from .core.image_handler import ImageHandler
from .config import PluginConfig


class KaleidoscopePlugin(Star):
    """万花筒图像处理插件"""

    def __init__(self, context: Context):
        super().__init__(context)

        # 加载配置
        self._config = self._load_config()

        # 初始化处理器
        self.image_handler = ImageHandler(self)

        self._initialized = False
        self._init_lock = asyncio.Lock()

        logger.info("万花筒插件已加载")
        logger.info(f"当前配置: 图像限制={self._config.image_size_limit_mb}MB, "
                    f"GIF限制={self._config.gif_size_limit_mb}MB, "
                    f"GIF={'启用' if self._config.enable_gif else '禁用'}, "
                    f"频率限制={self._config.rate_limit_per_minute}次/分钟")

    def _load_config(self) -> PluginConfig:
        """延迟加载配置（兼容 AstrBot 启动流程）"""
        try:
            if hasattr(self, "context") and hasattr(self.context, "config"):
                return PluginConfig.load_from_dict(self.context.config)
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
        return PluginConfig()

    @property
    def config(self) -> PluginConfig:
        """配置属性（兼容 ConfigService 风格）"""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    # ---- 指令：万花筒（带 / 前缀） ----

    @filter.command("万花筒", alias={"kaleidoscope", "万花筒效果"})
    async def cmd_kaleidoscope(self, event: AstrMessageEvent):
        """生成万花筒图像效果"""
        await self._ensure_initialized()
        async for result in self.image_handler.process_kaleidoscope(event):
            yield result
        event.stop_event()

    # ---- 指令：倒放 ----

    @filter.command("倒放", alias={"reverse", "gif倒放"})
    async def cmd_reverse(self, event: AstrMessageEvent):
        """GIF 倒放（动图帧序反转，静图原样返回）"""
        await self._ensure_initialized()
        async for result in self.image_handler.process_kaleidoscope(event, "reverse"):
            yield result
        event.stop_event()

    # ---- 指令：万花筒帮助 ----

    @filter.command("万花筒帮助", alias={"kaleidoscope help", "万花筒说明"})
    async def cmd_help(self, event: AstrMessageEvent):
        """显示万花筒插件帮助信息"""
        help_text = """🔮 万花筒插件使用说明

指令:
• /万花筒 或 kaleidoscope - 生成万花筒效果

效果说明:
以图片为「基础元素」，在正方形画布上呈8个放射状分支排列。
每分支5层元素，越靠近中心越小，越靠边缘越大，
每个元素旋转使顶部朝外，形成万花筒透视效果。

使用方法:
1. 发送一张图片，然后 @机器人 说「万花筒」
2. 直接发送 /万花筒 并附带一张图片

支持格式: PNG, JPG, BMP, WebP, GIF（动图逐帧处理）

示例:
- 发一张风景照并说: @机器人 万花筒
- 发图同时: /万花筒 [图片]
- 发GIF动图: @机器人 万花筒"""
        yield event.plain_result(help_text)
        event.stop_event()

    # ---- 自然语言指令（无斜杠） ----

    @filter.event_message_type(EventMessageType.ALL)
    async def handle_plain_commands(self, event: AstrMessageEvent):
        """处理无斜杠的自然语言指令"""
        message_str = event.message_str.strip()

        # 匹配「万花筒」关键词
        plain_commands = {
            "/万花筒": "kaleidoscope",
            "万花筒": "kaleidoscope",
            "kaleidoscope": "kaleidoscope",
            "/倒放": "reverse",
            "倒放": "reverse",
            "reverse": "reverse",
            "/万花筒帮助": "help",
            "万花筒帮助": "help",
            "万花筒说明": "help",
        }

        actual_command = message_str
        # 处理 "@机器人 万花筒" 格式
        if " @" in message_str:
            parts = message_str.split("@", 1)
            actual_command = parts[0].strip()
        elif message_str.startswith("@"):
            parts = message_str.split(None, 2)
            if len(parts) >= 2:
                actual_command = parts[1].strip()

        if actual_command in plain_commands:
            mode = plain_commands[actual_command]

            if mode == "help":
                async for result in self.cmd_help(event):
                    yield result
            else:
                await self._ensure_initialized()
                async for result in self.image_handler.process_kaleidoscope(event, mode):
                    yield result
            event.stop_event()

    # ---- 初始化 ----

    async def _ensure_initialized(self):
        """确保插件已初始化"""
        async with self._init_lock:
            if self._initialized:
                return

            # 重新加载配置（可能在运行时被修改）
            self._config = self._load_config()
            self.image_handler = ImageHandler(self)

            self._initialized = True
            logger.info("万花筒插件初始化完成")

    # ---- 卸载 ----

    async def terminate(self):
        """插件卸载时清理资源"""
        try:
            if self.image_handler is not None:
                await self.image_handler.cleanup()
            logger.info("万花筒插件已成功卸载")
        except Exception as e:
            logger.error(f"插件卸载异常: {e}")
