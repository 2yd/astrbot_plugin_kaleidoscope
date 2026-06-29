# astrbot-plugin-kaleidoscope

> 🔮 万花筒图像处理插件，为图片生成六边形对称翻转的万花筒视觉效果。

A [AstrBot](https://github.com/AstrBotDevs/AstrBot) plugin that applies a kaleidoscope effect to images through hexagonal symmetry flipping and color enhancement.

## 使用方式

| 指令 | 说明 |
|------|------|
| `/万花筒` 或 `kaleidoscope` | 将图片处理为万花筒效果 |
| `/万花筒帮助` 或 `万花筒说明` | 显示使用帮助 |

**使用方法：**
1. 发送一张图片，然后 @机器人 说「万花筒」
2. 直接发送 `/万花筒` 并附带一张图片

**支持格式：** PNG / JPG / BMP / WebP

## 效果示例

| 原图 | 万花筒 |
|------|--------|
| 输入图片 | 六边形对称翻转 + 色彩增强 |

## 配置项

通过 AstrBot 管理面板可配置：

- `image_size_limit_mb` — 图像大小限制（默认 10MB）
- `processing_timeout` — 处理超时时间（默认 30s）
- `output_quality` — 输出质量（默认 85）
- `silent_mode` — 静默模式（默认关闭）
- `rate_limit_per_minute` — 频率限制（默认 10次/分钟）

## 依赖

- **Pillow** — 图像处理核心库
- **aiohttp** — 网络图片下载

## Links

- [AstrBot Plugin Development Docs (中文)](https://docs.astrbot.app/dev/star/plugin-new.html)
- [AstrBot Repo](https://github.com/AstrBotDevs/AstrBot)
