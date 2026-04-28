"""
飞书 Webhook 推送模块
调用飞书自定义机器人 Webhook API，发送富文本消息。
"""

import json
import logging
from typing import Dict, Any

import requests

logger = logging.getLogger(__name__)


class FeishuNotifier:
    """飞书机器人推送器"""

    def __init__(self, config: Dict[str, Any]):
        feishu_config = config.get("feishu", {})
        self.webhook_url = feishu_config.get("webhook_url", "")
        self.timeout = config.get("request", {}).get("timeout", 15)

    def send(self, message: Dict[str, Any]) -> bool:
        """
        发送消息到飞书群聊。

        Args:
            message: 飞书消息体（支持 text / post 类型）

        Returns:
            是否发送成功
        """
        if not self.webhook_url or "YOUR_WEBHOOK_TOKEN_HERE" in self.webhook_url:
            logger.error(
                "[飞书] Webhook 地址未配置！请在 config.yaml 中设置 feishu.webhook_url"
            )
            # 即使未配置也打印消息内容到日志，方便调试
            self._log_message_content(message)
            return False

        try:
            headers = {"Content-Type": "application/json; charset=utf-8"}
            payload = json.dumps(message, ensure_ascii=False)

            # 飞书消息体大小限制约 30KB，检查是否需要分段
            if len(payload.encode("utf-8")) > 28000:
                return self._send_chunked(message)

            resp = requests.post(
                self.webhook_url,
                data=payload.encode("utf-8"),
                headers=headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()

            result = resp.json()
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                logger.info("[飞书] 消息发送成功")
                return True
            else:
                logger.error(f"[飞书] 发送失败: {result}")
                return False

        except requests.RequestException as e:
            logger.error(f"[飞书] 请求异常: {e}")
            return False
        except Exception as e:
            logger.error(f"[飞书] 未知错误: {e}")
            return False

    def _send_chunked(self, message: Dict[str, Any]) -> bool:
        """分段发送过长的消息"""
        msg_type = message.get("msg_type", "text")

        if msg_type == "post":
            # 分段处理富文本消息
            post_content = (
                message.get("content", {})
                .get("post", {})
                .get("zh_cn", {})
            )
            title = post_content.get("title", "")
            content_lines = post_content.get("content", [])

            # 每段最多 15 行
            chunk_size = 15
            chunks = [
                content_lines[i: i + chunk_size]
                for i in range(0, len(content_lines), chunk_size)
            ]

            success = True
            for idx, chunk in enumerate(chunks):
                chunk_title = title if idx == 0 else f"{title}（续{idx}）"
                chunk_msg = {
                    "msg_type": "post",
                    "content": {
                        "post": {
                            "zh_cn": {
                                "title": chunk_title,
                                "content": chunk,
                            }
                        }
                    },
                }
                if not self.send(chunk_msg):
                    success = False
            return success
        else:
            # 纯文本消息直接发送（一般不会超长）
            return self.send(message)

    def _log_message_content(self, message: Dict[str, Any]) -> None:
        """将消息内容输出到日志（用于 Webhook 未配置时的调试）"""
        msg_type = message.get("msg_type", "text")
        if msg_type == "text":
            text = message.get("content", {}).get("text", "")
            logger.info(f"[飞书-预览]\n{text}")
        elif msg_type == "post":
            post = (
                message.get("content", {})
                .get("post", {})
                .get("zh_cn", {})
            )
            title = post.get("title", "")
            logger.info(f"[飞书-预览] 标题: {title}")
            for line in post.get("content", []):
                text_parts = []
                for elem in line:
                    text_parts.append(elem.get("text", ""))
                logger.info(f"[飞书-预览] {''.join(text_parts)}")
