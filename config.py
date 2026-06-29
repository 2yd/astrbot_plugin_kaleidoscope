"""
插件配置管理模块
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from astrbot.api import logger


@dataclass
class PluginConfig:
    """插件配置数据类"""

    # 文件大小限制
    image_size_limit_mb: int = 10
    gif_size_limit_mb: int = 15

    # 处理参数
    processing_timeout: int = 60
    output_quality: int = 85

    # 功能开关
    silent_mode: bool = False
    enable_auto_cleanup: bool = True
    enable_gif: bool = True

    # 清理设置
    keep_files_hours: int = 1

    # 频率限制
    rate_limit_per_minute: int = 10

    # 并发限制
    max_concurrent_tasks: int = 3

    # GIF 限制
    max_gif_frames: int = 200

    @property
    def max_image_size_bytes(self) -> int:
        return self.image_size_limit_mb * 1024 * 1024

    @property
    def max_gif_size_bytes(self) -> int:
        return self.gif_size_limit_mb * 1024 * 1024

    @property
    def rate_limit_enabled(self) -> bool:
        return self.rate_limit_per_minute > 0

    @classmethod
    def load_from_dict(cls, config_dict: Optional[Dict[str, Any]]) -> "PluginConfig":
        if not config_dict:
            return cls()

        try:
            def safe_get(key: str, default, type_):
                value = config_dict.get(key, default)
                if value is None:
                    return default
                try:
                    if type_ == bool:
                        if isinstance(value, str):
                            return value.lower() in ("true", "1", "yes")
                        return bool(value)
                    return type_(value)
                except (ValueError, TypeError):
                    logger.warning(f"配置项 [{key}] 类型错误，使用默认值: {default}")
                    return default

            return cls(
                image_size_limit_mb=safe_get("image_size_limit_mb", 10, int),
                gif_size_limit_mb=safe_get("gif_size_limit_mb", 15, int),
                processing_timeout=safe_get("processing_timeout", 60, int),
                output_quality=safe_get("output_quality", 85, int),
                silent_mode=safe_get("silent_mode", False, bool),
                enable_auto_cleanup=safe_get("enable_auto_cleanup", True, bool),
                enable_gif=safe_get("enable_gif", True, bool),
                keep_files_hours=safe_get("keep_files_hours", 1, int),
                rate_limit_per_minute=safe_get("rate_limit_per_minute", 10, int),
                max_concurrent_tasks=safe_get("max_concurrent_tasks", 3, int),
                max_gif_frames=safe_get("max_gif_frames", 200, int),
            )
        except Exception as e:
            logger.error(f"配置解析失败，使用默认配置: {e}", exc_info=True)
            return cls()
