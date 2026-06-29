"""
消息解析工具模块
"""

from typing import List, Optional
import astrbot.api.message_components as Comp
from astrbot.api import logger


class MessageUtils:
    """消息解析工具类"""

    @staticmethod
    def extract_image_sources(event) -> List[str]:
        """从消息中提取图像源（URL / base64 / 本地文件）"""
        image_sources = []

        try:
            messages = event.get_messages()
            if not messages:
                return image_sources

            for component in messages:
                if isinstance(component, Comp.Image):
                    url = MessageUtils._extract_from_image_component(component)
                    if url:
                        image_sources.append(url)

                elif isinstance(component, Comp.Reply):
                    if hasattr(component, "chain") and component.chain:
                        for reply_component in component.chain:
                            if isinstance(reply_component, Comp.Image):
                                url = MessageUtils._extract_from_image_component(reply_component)
                                if url:
                                    image_sources.append(url)

            logger.debug(f"提取到 {len(image_sources)} 个图像源")
            return image_sources

        except Exception as e:
            logger.error(f"提取图像源失败: {e}")
            return []

    @staticmethod
    def _extract_from_image_component(component: Comp.Image) -> Optional[str]:
        """从Image组件提取图像URL或数据"""
        if hasattr(component, "url") and component.url:
            return component.url

        if hasattr(component, "file") and component.file:
            if isinstance(component.file, str):
                return component.file

        for attr_name in ["data", "path", "content"]:
            if hasattr(component, attr_name):
                attr_value = getattr(component, attr_name)
                if attr_value and isinstance(attr_value, str):
                    return attr_value

        return None
