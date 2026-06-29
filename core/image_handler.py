"""
图像处理主逻辑
"""

import asyncio
import base64
import hashlib
import tempfile
import time
from pathlib import Path
from typing import Optional, List
from astrbot.api import logger
from astrbot.api.star import StarTools
import astrbot.api.message_components as Comp

from ..constants import PLUGIN_NAME
from ..utils.file_utils import FileUtils
from ..utils.message_utils import MessageUtils
from ..image_processor import KaleidoscopeProcessor


class ImageHandler:
    """万花筒图像处理器"""

    TEMP_FILE_PREFIXES = ["kaleido_tmp_", "kaleido_downloaded_", "kaleido_base64_"]
    RATE_LIMIT_WINDOW_SECONDS = 60

    def __init__(self, config_service, plugin_name: str = None):
        self.config_service = config_service
        self.config = config_service.config

        self.message_utils = MessageUtils()
        self.file_utils = FileUtils()
        self.plugin_name = plugin_name or PLUGIN_NAME

        # 数据目录
        self.data_dir = StarTools.get_data_dir(self.plugin_name)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 频率限制
        self._user_request_times: dict[str, list[float]] = {}
        self._rate_limit_lock = asyncio.Lock()
        self._processing_semaphore = asyncio.Semaphore(self.config.max_concurrent_tasks)

    # ---- 频率限制 ----

    async def check_rate_limit(self, user_id: str) -> tuple[bool, Optional[str]]:
        """检查用户请求频率限制"""
        if not self.config.rate_limit_enabled:
            return True, None

        current_time = time.time()
        window_start = current_time - self.RATE_LIMIT_WINDOW_SECONDS

        async with self._rate_limit_lock:
            requests = self._user_request_times.get(user_id, [])
            recent = [t for t in requests if t >= window_start]
            self._user_request_times[user_id] = recent

            if len(recent) >= self.config.rate_limit_per_minute:
                remaining = self.RATE_LIMIT_WINDOW_SECONDS - (current_time - min(recent))
                return False, f"请求过于频繁，请 {int(remaining)} 秒后再试"

            self._user_request_times[user_id].append(current_time)
            return True, None

    # ---- 主处理流程 ----

    async def process_kaleidoscope(self, event, mode: str = "kaleidoscope"):
        """处理万花筒请求的统一入口"""
        try:
            user_id = event.get_sender_id()
            allowed, error_msg = await self.check_rate_limit(user_id)

            if not allowed:
                yield self._error_msg(event, error_msg)
                return

            async with self._processing_semaphore:
                logger.info(f"开始处理万花筒请求，用户: {user_id}")

                # 1. 提取图像源
                image_sources = self.message_utils.extract_image_sources(event)
                if not image_sources:
                    yield self._error_msg(event, "未找到图像，请发送一张图片并 @机器人 说「万花筒」")
                    return

                # 2. 提示处理中（非静默模式）
            if not self.config.silent_mode:
                gif_hint = "（动图逐帧处理，请耐心等待）" if any(
                    s.lower().endswith(".gif") for s in image_sources
                ) else ""
                yield event.plain_result(f"🔄 正在生成万花筒效果...{gif_hint}")

                # 3. 逐个处理图像源
                processed = False
                for image_source in image_sources:
                    try:
                        input_path = await self._prepare_image_file(image_source)
                        if not input_path:
                            continue

                        async for result in self._process_single_image(event, input_path, mode, str(image_source)):
                            yield result
                            processed = True

                    except Exception as e:
                        logger.error(f"处理图像源失败 {image_source}: {e}", exc_info=True)
                        continue

                if not processed:
                    yield self._error_msg(event, "处理失败", "未能处理任何图像")

        except Exception as e:
            logger.error(f"处理指令异常: {e}", exc_info=True)
            yield self._error_msg(event, "处理失败", str(e))

    async def _process_single_image(self, event, input_path: Path, mode: str, source_info: str):
        """处理单个图像"""
        try:
            input_ext = input_path.suffix.lower() if input_path.suffix else None
            output_filename = self.file_utils.generate_filename(source_info, mode, input_ext)
            output_path = self.data_dir / output_filename

            logger.info(f"处理图像: {input_path} -> {output_path}")

            success, message = await KaleidoscopeProcessor.process_image(
                str(input_path), str(output_path), mode, self.config
            )

            # 清理输入临时文件
            self._cleanup_input_file(input_path)

            if success:
                yield self._result_msg(event, output_path, mode)
                # 安排输出文件清理
                if self.config.enable_auto_cleanup:
                    self._schedule_cleanup(output_path)
            else:
                logger.warning(f"处理失败: {message}")
                yield self._error_msg(event, "处理失败", message)

        except Exception as e:
            logger.error(f"处理单图像失败: {e}", exc_info=True)
            yield self._error_msg(event, "处理失败")

    # ---- 图像源准备 ----

    async def _prepare_image_file(self, image_source: str) -> Optional[Path]:
        """准备图像文件：下载URL / 解码base64 / 本地文件"""
        if image_source.startswith(("http://", "https://")):
            return await self._download_image(image_source)
        elif image_source.startswith("base64://"):
            return await self._decode_base64_image(image_source)
        else:
            return self._get_local_file(image_source)

    async def _download_image(self, url: str) -> Optional[Path]:
        """下载网络图片（根据格式应用不同大小限制）"""
        import aiohttp

        try:
            timeout = aiohttp.ClientTimeout(total=self.config.processing_timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.error(f"下载失败，状态码: {response.status}")
                        return None

                    data = await response.read()

            # 魔数检测格式
            ext = self.file_utils.detect_image_format_by_magic(data)
            if not ext:
                ext = self.file_utils.get_file_extension(url) or ".jpg"

            # 根据格式选择大小限制
            if ext == ".gif":
                if not self.config.enable_gif:
                    logger.warning("GIF 处理已禁用")
                    return None
                max_size = self.config.max_gif_size_bytes
                size_label = f"{self.config.gif_size_limit_mb}MB"
            else:
                max_size = self.config.max_image_size_bytes
                size_label = f"{self.config.image_size_limit_mb}MB"

            if len(data) > max_size:
                logger.error(f"图片超过大小限制: {len(data)} bytes > {max_size} bytes ({size_label})")
                return None

            return await self._save_temp_file(data, "downloaded", ext)

        except Exception as e:
            logger.error(f"下载图片失败 {url}: {e}")
            return None

    async def _decode_base64_image(self, base64_data: str) -> Optional[Path]:
        """解码 base64 图像"""
        try:
            if base64_data.startswith("base64://"):
                base64_data = base64_data[len("base64://"):]

            loop = asyncio.get_running_loop()
            image_data = await loop.run_in_executor(None, lambda: base64.b64decode(base64_data, validate=True))

            if len(image_data) > self.config.max_image_size_bytes:
                logger.error(f"解码后图像过大: {len(image_data)} bytes")
                return None

            ext = self.file_utils.detect_image_format_by_magic(image_data) or ".png"
            source_hash = hashlib.md5(base64_data.encode()).hexdigest()[:16]
            return await self._save_temp_file(image_data, f"base64_{source_hash}", ext)

        except Exception as e:
            logger.error(f"Base64解码失败: {e}")
            return None

    def _get_local_file(self, file_path: str) -> Optional[Path]:
        """获取本地文件"""
        try:
            path = Path(file_path)
            if path.is_absolute():
                logger.warning(f"拒绝绝对路径: {file_path}")
                return None

            safe_path = (self.data_dir / path).resolve()
            data_dir_resolved = self.data_dir.resolve()
            if safe_path.is_relative_to(data_dir_resolved) and safe_path.exists():
                return safe_path

            logger.warning(f"路径越界: {file_path}")
            return None
        except Exception as e:
            logger.warning(f"本地路径解析失败 {file_path}: {e}")
            return None

    async def _save_temp_file(self, data: bytes, prefix: str, extension: str) -> Optional[Path]:
        """保存临时文件"""
        try:
            unique_prefix = f"kaleido_{prefix}_"
            with tempfile.NamedTemporaryFile(
                prefix=unique_prefix,
                suffix=extension,
                delete=False,
                dir=str(self.data_dir),
            ) as tmp:
                tmp.write(data)
                return Path(tmp.name)
        except Exception as e:
            logger.error(f"保存临时文件失败: {e}")
            return None

    def _cleanup_input_file(self, file_path: Path):
        """清理输入临时文件"""
        if not file_path or not file_path.exists():
            return
        try:
            if file_path.parent == self.data_dir:
                filename = file_path.name.lower()
                for prefix in self.TEMP_FILE_PREFIXES:
                    if filename.startswith(prefix):
                        file_path.unlink()
                        return
        except Exception as e:
            logger.warning(f"清理输入文件失败: {e}")

    # ---- 消息构建 ----

    def _result_msg(self, event, output_path: Path, mode: str):
        """构建结果消息"""
        if self.config.silent_mode:
            return event.chain_result([Comp.Image(file=str(output_path))])
        else:
            desc = KaleidoscopeProcessor.get_mode_description(mode)
            return event.chain_result([
                Comp.Plain(text=f"✅ {desc}\n"),
                Comp.Image(file=str(output_path)),
            ])

    def _error_msg(self, event, message: str, detail: str = None):
        """构建错误消息"""
        if self.config.silent_mode:
            return event.plain_result(f"❌ {message}")
        else:
            full = f"❌ {message}"
            if detail:
                full += f"\n详情: {detail}"
            return event.plain_result(full)

    # ---- 清理 ----

    def _schedule_cleanup(self, file_path: Path):
        """安排延迟清理"""
        async def _delayed_cleanup():
            try:
                seconds = self.config.keep_files_hours * 3600
                if seconds > 0:
                    await asyncio.sleep(seconds)
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"已清理输出文件: {file_path.name}")
            except Exception as e:
                logger.warning(f"清理文件失败: {e}")

        asyncio.create_task(_delayed_cleanup())

    async def cleanup(self):
        """清理所有资源"""
        # 清理旧临时文件
        try:
            for f in self.data_dir.glob("kaleido_*"):
                if f.is_file():
                    try:
                        f.unlink()
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"批量清理失败: {e}")

        logger.info("ImageHandler 资源清理完成")
