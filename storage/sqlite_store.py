"""
SQLite 存储模块
替代 LanceDB，用于存储文章和重点推荐数据。
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SQLiteStore:
    """SQLite 数据存储"""

    def __init__(self, db_path: Optional[str] = None):
        """初始化 SQLite 存储"""
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "newsqoder.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
        logger.info(f"[SQLiteStore] 数据库初始化完成: {self.db_path}")

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化数据库表结构"""
        with self._get_conn() as conn:
            # 文章表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    summary TEXT,
                    source TEXT,
                    link TEXT NOT NULL,
                    category TEXT,
                    push_date TEXT,
                    published TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 重点推荐表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS featured (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    summary TEXT,
                    link TEXT NOT NULL,
                    category_tag TEXT DEFAULT '大模型优化方向',
                    source TEXT,
                    date TEXT,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 每日洞察表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    insight TEXT NOT NULL,
                    keywords TEXT,
                    category_stats TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()

    # ==================== 文章操作 ====================
    
    def add_article(self, article: Dict[str, Any]) -> bool:
        """添加文章"""
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO articles 
                    (id, title, summary, source, link, category, push_date, published)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    article.get("id", ""),
                    article.get("title", ""),
                    article.get("summary", ""),
                    article.get("source", ""),
                    article.get("link", ""),
                    article.get("category", ""),
                    article.get("push_date", ""),
                    article.get("published", "")
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[SQLiteStore] 添加文章失败: {e}")
            return False

    def get_articles(
        self, 
        category: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取文章列表"""
        query = "SELECT * FROM articles WHERE 1=1"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if date_from:
            query += " AND push_date >= ?"
            params.append(date_from)
        
        if date_to:
            query += " AND push_date <= ?"
            params.append(date_to)
        
        query += " ORDER BY push_date DESC LIMIT ?"
        params.append(limit)
        
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def search_articles(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索文章（标题和摘要）"""
        search_term = f"%{query}%"
        
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM articles 
                WHERE title LIKE ? OR summary LIKE ?
                ORDER BY push_date DESC
                LIMIT ?
            """, (search_term, search_term, limit)).fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            
            dates = [row[0] for row in conn.execute(
                "SELECT DISTINCT push_date FROM articles ORDER BY push_date DESC"
            ).fetchall()]
            
            categories = {}
            for row in conn.execute(
                "SELECT category, COUNT(*) FROM articles GROUP BY category"
            ).fetchall():
                categories[row[0]] = row[1]
            
            return {
                "total": total,
                "dates": dates,
                "categories": categories
            }

    # ==================== 重点推荐操作 ====================
    
    def add_featured(self, article: Dict[str, Any]) -> bool:
        """添加重点推荐"""
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO featured 
                    (title, summary, link, category_tag, source, date, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    article.get("title", ""),
                    article.get("summary", ""),
                    article.get("link", ""),
                    article.get("category_tag", "大模型优化方向"),
                    article.get("source", ""),
                    article.get("date", ""),
                    article.get("sort_order", 0)
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[SQLiteStore] 添加重点推荐失败: {e}")
            return False

    def get_featured(self, category_tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取重点推荐列表"""
        query = "SELECT * FROM featured WHERE 1=1"
        params = []
        
        if category_tag:
            query += " AND category_tag = ?"
            params.append(category_tag)
        
        query += " ORDER BY sort_order ASC, created_at DESC"
        
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def clear_featured(self, category_tag: Optional[str] = None) -> bool:
        """清空重点推荐"""
        try:
            with self._get_conn() as conn:
                if category_tag:
                    conn.execute("DELETE FROM featured WHERE category_tag = ?", (category_tag,))
                else:
                    conn.execute("DELETE FROM featured")
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[SQLiteStore] 清空重点推荐失败: {e}")
            return False

    # ==================== 每日洞察操作 ====================
    
    def add_insight(self, date: str, insight: str, keywords: Optional[str] = None, category_stats: Optional[str] = None) -> bool:
        """添加每日洞察"""
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO daily_insights (date, insight, keywords, category_stats)
                    VALUES (?, ?, ?, ?)
                """, (date, insight, keywords, category_stats))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[SQLiteStore] 添加洞察失败: {e}")
            return False
    
    def get_insights_by_date(self, date: str) -> List[Dict[str, Any]]:
        """获取指定日期的洞察"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_insights WHERE date = ? ORDER BY id",
                (date,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def clear_insights_by_date(self, date: str) -> bool:
        """清空指定日期的洞察"""
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM daily_insights WHERE date = ?", (date,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[SQLiteStore] 清空洞察失败: {e}")
            return False

    # ==================== 每日洞察操作 ====================
    
    def add_insight(self, date: str, insight: str, keywords: Optional[str] = None, category_stats: Optional[str] = None) -> bool:
        """添加每日洞察"""
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO daily_insights (date, insight, keywords, category_stats)
                    VALUES (?, ?, ?, ?)
                """, (date, insight, keywords, category_stats))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[SQLiteStore] 添加洞察失败: {e}")
            return False
    
    def get_insights_by_date(self, date: str) -> List[Dict[str, Any]]:
        """获取指定日期的洞察"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_insights WHERE date = ? ORDER BY id",
                (date,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def clear_insights_by_date(self, date: str) -> bool:
        """清空指定日期的洞察"""
        try:
            with self._get_conn() as conn:
                conn.execute("DELETE FROM daily_insights WHERE date = ?", (date,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"[SQLiteStore] 清空洞察失败: {e}")
            return False
