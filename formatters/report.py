"""
日报格式化生成器
按照指定格式组装日报内容，生成纯文本和飞书富文本两种格式。
"""

import logging
import re
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ReportFormatter:
    """日报格式化器"""

    def format_text(
        self,
        classified: Dict[str, List[Dict[str, Any]]],
        insights: List[str],
    ) -> str:
        """生成纯文本格式的日报"""
        today = datetime.now().strftime("%Y年%m月%d日")
        lines = [f"【NewsQoder · 智驾AI日报】{today}", ""]

        # 智能驾驶产业
        lines.append("🔹 智能驾驶产业")
        if classified.get("ad_industry"):
            for article in classified["ad_industry"]:
                lines.append(self._format_article_text(article))
        else:
            lines.append("- 今日暂无重要动态")
        lines.append("")

        # AI产业
        lines.append("🔹 AI产业")
        if classified.get("ai_industry"):
            for article in classified["ai_industry"]:
                lines.append(self._format_article_text(article))
        else:
            lines.append("- 今日暂无重要动态")
        lines.append("")

        # 智能驾驶技术
        lines.append("🔹 智能驾驶技术")
        if classified.get("ad_tech"):
            for article in classified["ad_tech"]:
                lines.append(self._format_article_text(article))
        else:
            lines.append("- 今日暂无重要进展")
        lines.append("")

        # AI技术
        lines.append("🔹 AI技术")
        if classified.get("ai_tech"):
            for article in classified["ai_tech"]:
                lines.append(self._format_article_text(article))
        else:
            lines.append("- 今日暂无重要进展")
        lines.append("")

        # 机会洞察
        lines.append("🔹 机会洞察")
        for i, insight in enumerate(insights, 1):
            lines.append(f"- 核心趋势{i}：{insight}")
        lines.append("")

        return "\n".join(lines)

    def format_feishu_post(
        self,
        classified: Dict[str, List[Dict[str, Any]]],
        insights: List[str],
    ) -> Dict[str, Any]:
        """生成飞书富文本（post）格式的日报消息体"""
        today = datetime.now().strftime("%Y年%m月%d日")
        content = []

        # 智能驾驶产业
        content.append([{"tag": "text", "text": "🔹 智能驾驶产业"}])
        if classified.get("ad_industry"):
            for article in classified["ad_industry"]:
                content.append(self._format_article_post(article))
        else:
            content.append([{"tag": "text", "text": "今日暂无重要动态"}])
        content.append([{"tag": "text", "text": ""}])

        # AI产业
        content.append([{"tag": "text", "text": "🔹 AI产业"}])
        if classified.get("ai_industry"):
            for article in classified["ai_industry"]:
                content.append(self._format_article_post(article))
        else:
            content.append([{"tag": "text", "text": "今日暂无重要动态"}])
        content.append([{"tag": "text", "text": ""}])

        # 智能驾驶技术
        content.append([{"tag": "text", "text": "🔹 智能驾驶技术"}])
        if classified.get("ad_tech"):
            for article in classified["ad_tech"]:
                content.append(self._format_article_post(article))
        else:
            content.append([{"tag": "text", "text": "今日暂无重要进展"}])
        content.append([{"tag": "text", "text": ""}])

        # AI技术
        content.append([{"tag": "text", "text": "🔹 AI技术"}])
        if classified.get("ai_tech"):
            for article in classified["ai_tech"]:
                content.append(self._format_article_post(article))
        else:
            content.append([{"tag": "text", "text": "今日暂无重要进展"}])
        content.append([{"tag": "text", "text": ""}])

        # 机会洞察
        content.append([{"tag": "text", "text": "🔹 机会洞察"}])
        for i, insight in enumerate(insights, 1):
            content.append(
                [{"tag": "text", "text": f"- 核心趋势{i}：{insight}"}]
            )

        return {
            "msg_type": "post",
            "content": {
                "post": {
                    "zh_cn": {
                        "title": f"【NewsQoder · 智驾AI日报】{today}",
                        "content": content,
                    }
                }
            },
        }

    @staticmethod
    def format_no_update_message() -> Dict[str, Any]:
        """生成无重要更新时的飞书消息体"""
        today = datetime.now().strftime("%Y年%m月%d日")
        return {
            "msg_type": "text",
            "content": {
                "text": f"【NewsQoder · 智驾AI日报】{today}\n\n今日智能驾驶与AI领域暂无重大更新。"
            },
        }

    @staticmethod
    def _clean_summary(summary: str) -> str:
        """清洗摘要，去除非核心信息"""
        if not summary:
            return ""
        # 去除公众号推荐语
        summary = re.sub(r'#?欢迎关注.*?公众号[^。]*[。]?', '', summary)
        summary = re.sub(r'微信号[：:]\S+[,，）\)\s]?', '', summary)
        summary = re.sub(r'更多精彩内容.*?为您奉上[。]?', '', summary)
        # 去除各种"点击查看"提示
        summary = re.sub(r'(详情)?请?点击查看(原文|详情|链接)[>>。]?', '', summary)
        summary = re.sub(r'点击查看原文>?', '', summary)
        # 去除来源/时间标记
        summary = re.sub(r'来源[：:][^，。]{1,20}[，。]?', '', summary)
        # 去除 "36氪获悉" "硬氪获悉" 等开头
        summary = re.sub(r'^(\d+氪|硬氪)(获悉|了解到|首发)[，,]\s*', '', summary)
        # 去除残留空白和标点
        summary = re.sub(r'^[\s,，、；;：:]+', '', summary)
        summary = re.sub(r'\s+', ' ', summary).strip()
        return summary

    def _format_article_text(self, article: Dict[str, Any]) -> str:
        """格式化单篇文章为纯文本行：标题 + 精简摘要"""
        title = article.get("title", "")
        summary = self._clean_summary(article.get("summary", ""))

        if len(summary) > 50:
            summary = summary[:47] + "..."

        if summary:
            return f"- {title}：{summary}"
        return f"- {title}"

    def _format_article_post(self, article: Dict[str, Any]) -> List[Dict[str, Any]]:
        """格式化单篇文章为飞书富文本行"""
        title = article.get("title", "")
        summary = self._clean_summary(article.get("summary", ""))
        link = article.get("link", "")

        if len(summary) > 50:
            summary = summary[:47] + "..."

        elements = [{"tag": "text", "text": "- "}]

        if link:
            elements.append({"tag": "a", "text": title, "href": link})
        else:
            elements.append({"tag": "text", "text": title})

        if summary:
            elements.append({"tag": "text", "text": f"：{summary}"})

        return elements
