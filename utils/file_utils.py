"""
文件处理工具模块
"""

import os
import re
import hashlib
import secrets
import time as time_module
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs

from astrbot.api import logger
from astrbot.api.star import StarTools


class FileUtils:
    """文件处理工具类"""

    SUPPORTED_STATIC_FORMATS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
    SUPPORTED_FORMATS = SUPPORTED_STATIC_FORMATS

    MAGIC_BYTES = {
        "png": (b"\x89PNG\r\n\x1a\n", 8),
        "jpeg": (b"\xff\xd8\xff", 3),
        "webp": (b"RIFF", 4, b"WEBP", 8),
        "bmp": (b"BM", 2),
    }

    URL_LENGTH_THRESHOLD = 1000

    def __init__(self, plugin_name: str = "astrbot_plugin_kaleidoscope"):
        self.data_dir = FileUtils.ensure_data_dir(plugin_name)

    @staticmethod
    def ensure_data_dir(plugin_name: str) -> Path:
        data_dir = StarTools.get_data_dir(plugin_name)
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    @staticmethod
    def get_file_extension(url_or_path: str) -> Optional[str]:
        """从URL或路径中提取文件扩展名"""
        try:
            parsed = urlparse(url_or_path)
            path = parsed.path
            match = re.search(r"\.([a-zA-Z0-9]+)$", path)
            if match:
                ext = f".{match.group(1).lower()}"
                if ext in FileUtils.SUPPORTED_FORMATS:
                    return ext

            query_params = parse_qs(parsed.query)
            for param_name in ["format", "type", "ext"]:
                if param_name in query_params:
                    param_value = query_params[param_name][0].lower()
                    ext = f".{param_value}" if not param_value.startswith(".") else param_value
                    if ext in FileUtils.SUPPORTED_FORMATS:
                        return ext
            return None
        except Exception:
            return None

    @staticmethod
    def validate_image_size(image_path: str, max_size_bytes: int) -> Tuple[bool, str]:
        """验证图像文件大小"""
        try:
            file_size = os.path.getsize(image_path)
            if file_size > max_size_bytes:
                file_size_mb = file_size / 1024 / 1024
                max_size_mb = max_size_bytes / 1024 / 1024
                return False, f"文件过大（{file_size_mb:.1f}MB），最大允许：{max_size_mb:.0f}MB"
            return True, ""
        except Exception as e:
            return False, f"无法获取文件大小: {str(e)}"

    @staticmethod
    def detect_image_format_by_magic(data: bytes) -> Optional[str]:
        """通过魔数检测图像格式"""
        if len(data) < 12:
            return None

        magic = FileUtils.MAGIC_BYTES
        if data[:8] == magic["png"][0]:
            return ".png"
        if data[:3] == magic["jpeg"][0]:
            return ".jpg"
        if data[:4] == magic["webp"][0] and data[8:12] == magic["webp"][2]:
            return ".webp"
        if data[:2] == magic["bmp"][0]:
            return ".bmp"
        return None

    def generate_filename(self, source_info: str, mode: str, input_ext: Optional[str] = None) -> str:
        """生成唯一的文件名"""
        if len(source_info) > self.URL_LENGTH_THRESHOLD:
            content_hash = hashlib.md5(source_info.encode()).hexdigest()[:16]
            hash_input = f"{content_hash}_{mode}"
        else:
            hash_input = f"{source_info}_{mode}"

        timestamp = int(time_module.time())
        random_token = secrets.token_hex(4)
        hash_input = f"{hash_input}_{timestamp}_{random_token}"
        file_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:12]

        if input_ext and input_ext in FileUtils.SUPPORTED_FORMATS:
            ext = input_ext
        else:
            ext = FileUtils.get_file_extension(source_info) or ".png"

        filename = f"kaleido_{mode}_{file_hash}{ext}"
        counter = 0
        original_filename = filename
        while (self.data_dir / filename).exists():
            counter += 1
            filename = f"kaleido_{mode}_{file_hash}_{counter}{ext}"
        return filename
