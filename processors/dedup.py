"""
内容去重与降噪模块
基于标题相似度和向量库历史记录进行去重，剔除重复和低质量信息。
"""

import logging
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class Deduplicator:
    """文章去重器 - 支持本地相似度去重和向量库历史去重"""

    def __init__(self, similarity_threshold: float = 0.65, history_days: int = 3):
        """
        Args:
            similarity_threshold: 标题相似度阈值，超过此值视为重复
            history_days: 向量库历史去重天数（默认3天）
        """
        self.similarity_threshold = similarity_threshold
        self.history_days = history_days
        self._vector_store = None

    def _get_vector_store(self):
        """延迟初始化向量库连接"""
        if self._vector_store is None:
            try:
                import sys
                from pathlib import Path
                sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                from storage.vector_store import VectorStore
                self._vector_store = VectorStore()
            except Exception as e:
                logger.warning(f"[去重] 向量库连接失败: {e}")
        return self._vector_store

    def deduplicate(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对文章列表进行去重和降噪"""
        if not articles:
            return []

        # Step 1: 基本降噪 - 移除标题过短或无效的条目
        cleaned = [a for a in articles if self._is_valid(a)]
        logger.info(f"[去重] 降噪后剩余 {len(cleaned)}/{len(articles)} 篇")

        # Step 2: 向量库历史去重（避免3天内重复推送同一事件）
        cleaned = self._dedup_by_history(cleaned)
        logger.info(f"[去重] 历史去重后剩余 {len(cleaned)} 篇")

        # Step 3: 按相关性评分降序排列（保留高质量内容）
        cleaned.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        # Step 4: 基于标题相似度去重
        unique_articles = []
        for article in cleaned:
            if not self._is_duplicate(article, unique_articles):
                unique_articles.append(article)

        logger.info(f"[去重] 相似度去重后剩余 {len(unique_articles)}/{len(cleaned)} 篇")
        return unique_articles

    def _dedup_by_history(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """基于向量库历史记录去重（避免近N天重复推送）"""
        vector_store = self._get_vector_store()
        if not vector_store:
            return articles

        try:
            # 计算查询日期范围
            date_to = datetime.now().strftime("%Y-%m-%d")
            date_from = (datetime.now() - timedelta(days=self.history_days)).strftime("%Y-%m-%d")

            # 获取近N天历史标题集合
            history_df = vector_store.table.to_pandas()
            if len(history_df) == 0:
                return articles

            # 筛选日期范围内的记录
            history_df = history_df[
                (history_df["push_date"] >= date_from) &
                (history_df["push_date"] <= date_to)
            ]
            history_titles = set(history_df["title"].tolist())

            if not history_titles:
                return articles

            # 过滤当前文章：标题与历史记录相似度超过阈值的视为重复
            filtered = []
            for article in articles:
                title = article.get("title", "")
                is_duplicate = False
                for hist_title in history_titles:
                    similarity = SequenceMatcher(None, title, hist_title).ratio()
                    if similarity >= self.similarity_threshold:
                        logger.debug(f"[历史去重] 重复: '{title}' ≈ '{hist_title}' ({similarity:.2f})")
                        is_duplicate = True
                        break
                if not is_duplicate:
                    filtered.append(article)

            removed_count = len(articles) - len(filtered)
            if removed_count > 0:
                logger.info(f"[历史去重] 过滤近{self.history_days}天已推送文章 {removed_count} 篇")
            return filtered

        except Exception as e:
            logger.warning(f"[历史去重] 查询失败: {e}")
            return articles

    def _is_valid(self, article: Dict[str, Any]) -> bool:
        """检查文章是否有效（非低质量）"""
        title = article.get("title", "")
        # 标题至少 5 个字符
        if len(title) < 5:
            return False
        # 过滤明显的非新闻内容
        noise_patterns = [
            # 广告/营销类
            "广告", "招聘", "活动报名", "直播预告", "课程推荐",
            "氪星晚报", "8点1氪", "我们寻找", "征集开始",
            "Under36", "36Under",
            # 股市/金融无关
            "涨停", "跌停", "龙虎榜", "股票异动", "大宗交易",
            "司法冻结", "被留置", "被逮捕", "立案调查",
            # 非相关行业
            "星巴克", "美团", "饼干", "咖啡", "白酒", "茅台",
            "房地产", "楼市", "房价", "物业",
            "医美", "化妆品", "娱乐", "综艺",
            # 安保/无关业务
            "安保运营",
        ]
        for pattern in noise_patterns:
            if pattern in title:
                return False
        return True

    def _is_duplicate(
        self, article: Dict[str, Any], existing: List[Dict[str, Any]]
    ) -> bool:
        """检查文章是否与已有列表中的条目重复"""
        title = article.get("title", "")
        for existing_article in existing:
            existing_title = existing_article.get("title", "")
            similarity = SequenceMatcher(None, title, existing_title).ratio()
            if similarity >= self.similarity_threshold:
                logger.debug(
                    f"[去重] 重复: '{title}' ≈ '{existing_title}' "
                    f"(相似度: {similarity:.2f})"
                )
                return True
        return False
