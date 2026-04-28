"""
RSS 新闻源采集器
通过 feedparser 解析 RSS/Atom feed，提取最近 24 小时内的文章。
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# 核心领域关键词 - 文章必须至少匹配其中一个才算与智驾/AI相关
CORE_DOMAIN_KEYWORDS = [
    # 智能驾驶
    "自动驾驶", "智能驾驶", "智驾", "无人驾驶", "辅助驾驶",
    "NOA", "Robotaxi", "L3", "L4", "城市领航",
    # AI 核心
    "AI", "人工智能", "大模型", "LLM", "GPT", "多模态", "智能体", "Agent",
    "端到端", "VLA", "世界模型", "Transformer", "深度学习", "机器学习",
    "AIGC", "生成式AI", "GenAI",
    # 硬件/算力
    "激光雷达", "感知算法", "BEV", "4D雷达",
    "算力", "GPU", "NPU", "AI芯片",
    # 机器人
    "机器人", "具身智能",
    # 企业/品牌
    "Apollo", "小马智行", "文远知行", "地平线", "Waymo", "特斯拉FSD",
    "OpenAI", "Anthropic", "DeepSeek", "Qwen", "通义", "Claude",
    "小鹏", "理想汽车", "蔚来", "华为", "小米汽车", "百度",
    # 补充
    "神经网络", "推理", "训练", "开源模型", "token", "芯片",
]

# 黑名单模式 - 标题匹配这些模式的直接丢弃
BLACKLIST_PATTERNS = [
    "星巴克", "瑞幸", "咖啡", "餐饮", "外卖", "美团",
    "股票异动", "涨停", "跌停", "龙虎榜", "大宗交易", "股价",
    "被留置", "被逮捕", "违规", "立案调查", "罚款",
    "房地产", "楼市", "房价", "物业",
    "白酒", "茅台", "医美", "化妆品",
    "娱乐", "综艺", "明星", "选秀",
    "体育", "球赛", "赛事",
    "8点1氪", "氪星晚报", "征集开始", "我们寻找",
    "活动报名", "直播预告", "课程推荐", "广告", "招聘",
    "Under36", "36Under",
    "安保运营", "司法冻结",
    "潘兴广场", "黄金", "原油",
    "现金加股票收购", "环球音乐",
]


class RSSCollector:
    """RSS 源采集器"""

    def __init__(self, config: Dict[str, Any]):
        self.sources = config.get("rss_sources", [])
        self.request_config = config.get("request", {})
        self.timeout = self.request_config.get("timeout", 15)
        self.retry = self.request_config.get("retry", 3)
        self.delay = self.request_config.get("delay", 2)
        self.user_agent = self.request_config.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        # 最低关键词匹配数
        self.min_relevance = 1

    def collect_all(self) -> List[Dict[str, Any]]:
        """采集所有 RSS 源的文章"""
        all_articles = []
        for source in self.sources:
            try:
                articles = self._collect_source(source)
                all_articles.extend(articles)
                logger.info(f"[RSS] {source['name']}: 采集到 {len(articles)} 篇文章")
            except Exception as e:
                logger.error(f"[RSS] {source['name']} 采集失败: {e}")
            time.sleep(self.delay)
        return all_articles

    def _collect_source(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """采集单个 RSS 源"""
        url = source["url"]
        name = source["name"]
        category = source.get("category", "general")
        source_keywords = source.get("keywords", [])

        feed_content = self._fetch_feed(url)
        if not feed_content:
            return []

        feed = feedparser.parse(feed_content)
        if feed.bozo:
            logger.warning(f"[RSS] {name}: Feed 解析有警告 - {feed.bozo_exception}")
            if not feed.entries:
                # 尝试用 lxml 修复后重新解析
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(feed_content, "lxml-xml")
                    fixed_content = str(soup)
                    feed = feedparser.parse(fixed_content)
                    if feed.entries:
                        logger.info(f"[RSS] {name}: lxml 修复后成功解析到 {len(feed.entries)} 条")
                    else:
                        logger.warning(f"[RSS] {name}: 修复后仍无条目")
                        return []
                except Exception as e:
                    logger.warning(f"[RSS] {name}: lxml 修复失败 - {e}")
                    return []

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=48)
        articles = []

        for entry in feed.entries:
            try:
                article = self._parse_entry(entry, name, category, source_keywords)
                if article is None:
                    continue

                # 过滤 24 小时以外的文章
                pub_date = article.get("published_dt")
                if pub_date and pub_date < cutoff_time:
                    continue

                # 黑名单过滤
                title = article.get("title", "")
                if any(bp in title for bp in BLACKLIST_PATTERNS):
                    logger.debug(f"[RSS] {name}: 黑名单过滤 - {title}")
                    continue

                # 核心领域相关性检查：标题+摘要必须包含至少一个核心领域关键词
                text = f"{title} {article.get('summary', '')}"
                core_match = any(ck.lower() in text.lower() for ck in CORE_DOMAIN_KEYWORDS)
                if not core_match:
                    logger.debug(f"[RSS] {name}: 非核心领域 - {title}")
                    continue

                # 源关键词匹配门槛：综合源需要至少2个匹配，AI专业源只需1个
                min_rel = source.get("min_relevance", self.min_relevance)
                relevance = article.get("relevance_score", 0)
                if source_keywords and relevance < min_rel:
                    logger.debug(f"[RSS] {name}: 相关度不足({relevance}) - {title}")
                    continue

                articles.append(article)
            except Exception as e:
                logger.debug(f"[RSS] {name}: 解析条目失败 - {e}")
                continue

        return articles

    def _fetch_feed(self, url: str) -> Optional[str]:
        """带重试的 Feed 内容获取"""
        headers = {"User-Agent": self.user_agent}
        for attempt in range(self.retry):
            try:
                resp = requests.get(url, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                return resp.text
            except requests.RequestException as e:
                logger.warning(f"[RSS] 请求失败 (第{attempt + 1}次): {url} - {e}")
                if attempt < self.retry - 1:
                    time.sleep(self.delay)
        return None

    def _parse_entry(
        self,
        entry: Any,
        source_name: str,
        category: str,
        source_keywords: List[str],
    ) -> Optional[Dict[str, Any]]:
        """解析单条 Feed 条目"""
        title = entry.get("title", "").strip()
        if not title:
            return None

        link = entry.get("link", "")
        summary = self._extract_summary(entry)
        published_dt = self._parse_date(entry)
        published_str = (
            published_dt.strftime("%Y-%m-%d %H:%M") if published_dt else ""
        )

        # 关键词相关性检查
        text = f"{title} {summary}"
        matched_keywords = [kw for kw in source_keywords if kw.lower() in text.lower()]

        return {
            "title": title,
            "link": link,
            "summary": summary[:200] if summary else "",
            "source": source_name,
            "category": category,
            "published": published_str,
            "published_dt": published_dt,
            "matched_keywords": matched_keywords,
            "relevance_score": len(matched_keywords),
        }

    @staticmethod
    def _extract_summary(entry: Any) -> str:
        """从 Feed 条目中提取摘要文本"""
        summary = entry.get("summary", "") or entry.get("description", "")
        if not summary:
            content = entry.get("content", [])
            if content:
                summary = content[0].get("value", "")

        # 去除 HTML 标签
        if summary and ("<" in summary):
            soup = BeautifulSoup(summary, "lxml")
            summary = soup.get_text(separator=" ", strip=True)

        # 清除摘要中的作者/编辑人名信息
        name_pattern = re.compile(
            r'(作者|文|编辑|记者|出品|来源|撰文|采写|策划)[\s]*[丨｜|\|/:：\s][\s]*[\u4e00-\u9fff]{2,4}'
        )
        while name_pattern.search(summary):
            summary = name_pattern.sub('', summary)
        summary = re.sub(r'^[\s,，、｜|]+', '', summary)

        return summary.strip()

    @staticmethod
    def _parse_date(entry: Any) -> Optional[datetime]:
        """解析 Feed 条目的发布时间"""
        time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if time_struct:
            try:
                dt = datetime(*time_struct[:6], tzinfo=timezone.utc)
                return dt
            except (TypeError, ValueError):
                pass

        # 尝试从字符串解析
        date_str = entry.get("published") or entry.get("updated", "")
        if date_str:
            for fmt in [
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S GMT",
            ]:
                try:
                    return datetime.strptime(date_str.strip(), fmt).replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    continue
        return None
