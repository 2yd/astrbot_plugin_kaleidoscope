# astrbot-plugin-kaleidoscope

> 🔮 万花筒图像处理插件，以放射状分支布局生成万花筒透视效果。

A [AstrBot](https://github.com/AstrBotDevs/AstrBot) plugin that creates kaleidoscope effects using radial branch layouts with perspective scaling.

## 效果原理

1. 将图片缩放为「基础元素」（长边 200px）
2. 在 1000×1000 白色画布上，以中心为圆心
3. **8 个分支**呈 45° 均分放射状排列
4. 每分支 **5 层**元素副本，缩放和距离从内到外递增
5. 每个元素旋转使**顶部背对圆心、朝向外侧**

```
         🌸
      🌸  🌸
   🌸   🌸   🌸
🌸  🌸   🎯   🌸  🌸       ← 8分支 × 5层 = 40个元素
   🌸   🌸   🌸
      🌸  🌸
         🌸
```

## 使用方式

| 指令 | 说明 |
|------|------|
| `/万花筒` 或 `kaleidoscope` | 生成万花筒效果 |
| `/万花筒帮助` | 显示帮助 |

**使用方法：**
1. 发送一张图片，然后 @机器人 说「万花筒」
2. 直接发送 `/万花筒` 并附带一张图片
3. **支持 GIF 动图**：发送动图即可逐帧处理

**支持格式：** PNG / JPG / BMP / WebP / GIF

## 配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `image_size_limit_mb` | 10 | 静态图大小限制 |
| `gif_size_limit_mb` | 15 | GIF 大小限制 |
| `enable_gif` | true | 启用 GIF 处理 |
| `max_gif_frames` | 200 | GIF 最大帧数 |
| `processing_timeout` | 60s | 处理超时（GIF 建议≥60s） |
| `output_quality` | 85 | 输出质量 |
| `silent_mode` | false | 静默模式 |
| `rate_limit_per_minute` | 10 | 频率限制 |

## 依赖

- **Pillow** — 图像处理（含 GIF 帧处理）
- **aiohttp** — 网络图片下载

## Links

- [AstrBot Plugin Development Docs](https://docs.astrbot.app/dev/star/plugin-new.html)
- [AstrBot Repo](https://github.com/AstrBotDevs/AstrBot)
