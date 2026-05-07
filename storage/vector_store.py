"""
向量数据库存储模块
使用 SQLite 将每日推送的资讯持久化存储，支持检索和历史查询。
（原 LanceDB 实现已替换为 SQLite，避免 Windows DLL 兼容性问题）
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class VectorStore:
    """基于 SQLite 的持久化存储（兼容原接口）"""

    def __init__(self, db_path: Optional[str] = None):
        """
        Args:
            db_path: 数据库持久化路径，默认为项目根目录下的 data/newsqoder.db
        """
        self.store = SQLiteStore(db_path)
        logger.info("[VectorStore] 使用 SQLite 后端")

    def store_articles(
        self,
        classified: Dict[str, List[Dict[str, Any]]],
        push_date: Optional[str] = None,
    ) -> int:
        """
        将分类后的文章批量存入向量库。

        Args:
            classified: 分类后的文章字典
            push_date: 推送日期，默认当天 YYYY-MM-DD

        Returns:
            新增存储的文章数量
        """
        if push_date is None:
            push_date = datetime.now().strftime("%Y-%m-%d")

        count = 0
        for category, articles in classified.items():
            for article in articles:
                title = article.get("title", "")
                summary = article.get("summary", "")
                source = article.get("source", "")
                link = article.get("link", "")
                published = article.get("published", "")
                display_category = article.get("display_category", category)

                doc_id = self._make_id(title, push_date)

                doc = {
                    "id": doc_id,
                    "title": title,
                    "summary": summary[:500] if summary else "",
                    "source": source,
                    "link": link,
                    "published": published,
                    "category": display_category,
                    "push_date": push_date,
                }

                if self.store.add_article(doc):
                    count += 1

        logger.info(f"[向量库] 新增 {count} 条记录")
        return count

    def search(
        self,
        query: str,
        n_results: int = 10,
        category: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        全文检索历史资讯。

        Args:
            query: 查询文本
            n_results: 返回结果数量
            category: 过滤分类
            date_from: 起始日期 YYYY-MM-DD
            date_to: 截止日期 YYYY-MM-DD

        Returns:
            匹配的文章列表
        """
        if query:
            # 使用搜索功能
            results = self.store.search_articles(query, limit=n_results)
            
            # 应用额外过滤
            if category:
                results = [r for r in results if r.get("category") == category]
            if date_from:
                results = [r for r in results if r.get("push_date", "") >= date_from]
            if date_to:
                results = [r for r in results if r.get("push_date", "") <= date_to]
            
            return results[:n_results]
        else:
            # 无查询词，使用筛选
            return self.store.get_articles(
                category=category,
                date_from=date_from,
                date_to=date_to,
                limit=n_results
            )

    def get_by_date(self, date: str) -> List[Dict[str, Any]]:
        """获取指定日期的所有推送记录"""
        return self.store.get_articles(date_from=date, date_to=date)

    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        return self.store.get_stats()

    # ==================== 重点推荐功能 ====================
    
    def add_featured(self, article: Dict[str, Any]) -> bool:
        """添加重点推荐文章"""
        return self.store.add_featured(article)
    
    def get_featured(self, category_tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取重点推荐列表"""
        return self.store.get_featured(category_tag)
    
    def clear_featured(self, category_tag: Optional[str] = None) -> bool:
        """清空重点推荐"""
        return self.store.clear_featured(category_tag)

    def store_insights(self, date: str, insights: List[str], keywords: Optional[Dict[str, Any]] = None, category_stats: Optional[Dict[str, Any]] = None) -> int:
        """保存每日洞察"""
        import json
        self.store.clear_insights_by_date(date)
        count = 0
        keywords_json = json.dumps(keywords, ensure_ascii=False) if keywords else None
        stats_json = json.dumps(category_stats, ensure_ascii=False) if category_stats else None
        for insight in insights:
            if self.store.add_insight(date, insight, keywords_json, stats_json):
                count += 1
        logger.info(f"[向量库] 保存 {count} 条洞察")
        return count

    def get_insights_by_date(self, date: str) -> List[Dict[str, Any]]:
        """获取指定日期的洞察"""
        return self.store.get_insights_by_date(date)

    @staticmethod
    def _make_id(title: str, date: str) -> str:
        """根据标题和日期生成唯一 ID"""
        raw = f"{date}:{title}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()
