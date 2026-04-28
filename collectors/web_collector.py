"""
网页爬虫采集器
对无 RSS 的站点进行网页抓取，提取标题、摘要、日期、链接。
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class WebCollector:
    """网页爬虫采集器"""

    def __init__(self, config: Dict[str, Any]):
        self.sources = config.get("web_sources", [])
        self.request_config = config.get("request", {})
        self.timeout = self.request_config.get("timeout", 15)
        self.retry = self.request_config.get("retry", 3)
        self.delay = self.request_config.get("delay", 2)
        self.user_agent = self.request_config.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self.filter_keywords = config.get("filter_keywords", {})

    def collect_all(self) -> List[Dict[str, Any]]:
        """采集所有网页源的文章"""
        all_articles = []
        for source in self.sources:
            try:
                articles = self._collect_source(source)
                all_articles.extend(articles)
                logger.info(f"[Web] {source['name']}: 采集到 {len(articles)} 篇文章")
            except Exception as e:
                logger.error(f"[Web] {source['name']} 采集失败: {e}")
            time.sleep(self.delay)
        return all_articles

    def _collect_source(self, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """采集单个网页源"""
        url = source["url"]
        name = source["name"]
        category = source.get("category", "general")
        selectors = source.get("selector", {})

        html = self._fetch_page(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        articles = []

        # 使用配置的选择器提取文章
        article_selector = selectors.get("article", "article")
        article_elements = soup.select(article_selector)

        if not article_elements:
            # 回退：尝试通用选择器
            article_elements = soup.select("article, .article, .post, .news-item, .item")

        for elem in article_elements:
            try:
                article = self._parse_article(elem, selectors, name, category, url)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"[Web] {name}: 解析文章元素失败 - {e}")
                continue

        return articles

    def _fetch_page(self, url: str) -> Optional[str]:
        """带重试的页面获取"""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        for attempt in range(self.retry):
            try:
                resp = requests.get(url, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding
                return resp.text
            except requests.RequestException as e:
                logger.warning(f"[Web] 请求失败 (第{attempt + 1}次): {url} - {e}")
                if attempt < self.retry - 1:
                    time.sleep(self.delay)
        return None

    def _parse_article(
        self,
        elem: Any,
        selectors: Dict[str, str],
        source_name: str,
        category: str,
        base_url: str,
    ) -> Optional[Dict[str, Any]]:
        """解析单个文章元素"""
        # 提取标题
        title_selector = selectors.get("title", "h2, h3, .title")
        title_elem = elem.select_one(title_selector)
        if not title_elem:
            title_elem = elem.select_one("h2, h3, h4, .title, a")
        title = title_elem.get_text(strip=True) if title_elem else ""
        if not title:
            return None

        # 提取链接
        link_selector = selectors.get("link", "a")
        link_elem = elem.select_one(link_selector)
        if not link_elem and title_elem:
            link_elem = title_elem.find_parent("a") or title_elem.find("a")
        link = ""
        if link_elem:
            href = link_elem.get("href", "")
            if href.startswith("http"):
                link = href
            elif href.startswith("/"):
                # 拼接完整 URL
                from urllib.parse import urljoin
                link = urljoin(base_url, href)

        # 提取摘要
        summary_selector = selectors.get("summary", ".summary, .desc, p")
        summary_elem = elem.select_one(summary_selector)
        if not summary_elem:
            summary_elem = elem.select_one("p, .desc, .excerpt, .abstract")
        summary = summary_elem.get_text(strip=True) if summary_elem else ""

        # 提取日期
        date_selector = selectors.get("date", ".date, time, .time")
        date_elem = elem.select_one(date_selector)
        if not date_elem:
            date_elem = elem.select_one("time, .date, .time, .meta span")
        date_text = ""
        if date_elem:
            date_text = date_elem.get("datetime", "") or date_elem.get_text(strip=True)

        published_dt = self._parse_date_text(date_text)

        # 计算关键词相关性
        all_keywords = (
            self.filter_keywords.get("high_priority", [])
            + self.filter_keywords.get("medium_priority", [])
        )
        text = f"{title} {summary}"
        matched = [kw for kw in all_keywords if kw.lower() in text.lower()]

        return {
            "title": title,
            "link": link,
            "summary": summary[:200] if summary else "",
            "source": source_name,
            "category": category,
            "published": published_dt.strftime("%Y-%m-%d %H:%M") if published_dt else date_text,
            "published_dt": published_dt,
            "matched_keywords": matched,
            "relevance_score": len(matched),
        }

    @staticmethod
    def _parse_date_text(date_text: str) -> Optional[datetime]:
        """尝试从文本中解析日期"""
        if not date_text:
            return None

        date_text = date_text.strip()

        # 常见中文日期格式
        patterns = [
            (r"(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})", "%Y-%m-%d %H:%M"),
            (r"(\d{4})-(\d{1,2})-(\d{1,2})", "%Y-%m-%d"),
            (r"(\d{4})年(\d{1,2})月(\d{1,2})日", None),
            (r"(\d{1,2})小时前", None),
            (r"(\d{1,2})分钟前", None),
        ]

        # ISO 格式
        for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(date_text, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

        # 相对时间：x小时前 / x分钟前
        hours_match = re.search(r"(\d+)\s*小时前", date_text)
        if hours_match:
            hours = int(hours_match.group(1))
            return datetime.now(timezone.utc) - timedelta(hours=hours)

        minutes_match = re.search(r"(\d+)\s*分钟前", date_text)
        if minutes_match:
            minutes = int(minutes_match.group(1))
            return datetime.now(timezone.utc) - timedelta(minutes=minutes)

        # 中文日期
        cn_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", date_text)
        if cn_match:
            y, m, d = int(cn_match.group(1)), int(cn_match.group(2)), int(cn_match.group(3))
            return datetime(y, m, d, tzinfo=timezone.utc)

        return None
