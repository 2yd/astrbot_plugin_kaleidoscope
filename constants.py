"""插件常量定义"""

import yaml
from pathlib import Path

PLUGIN_NAME = "astrbot_plugin_kaleidoscope"
PLUGIN_DESCRIPTION = "图像万花筒处理插件"


def _load_version() -> str:
    """从 metadata.yaml 读取版本号"""
    try:
        metadata_path = Path(__file__).parent / "metadata.yaml"
        if not metadata_path.exists():
            return "unknown"

        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = yaml.safe_load(f)

        version = metadata.get("version", "unknown")
        if version.startswith("v"):
            version = version[1:]
        return version

    except Exception:
        return "unknown"


PLUGIN_VERSION = _load_version()
