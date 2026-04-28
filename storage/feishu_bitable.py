"""
飞书 Bitable 存储模块
将文章数据存储到飞书多维表格，作为云端数据库使用。
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class FeishuBitableStore:
    """飞书 Bitable 存储"""

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        app_token: Optional[str] = None,
        table_id: Optional[str] = None,
        wiki_node_token: Optional[str] = None,
    ):
        """
        Args:
            app_id: 飞书应用 ID
            app_secret: 飞书应用 Secret
            app_token: Bitable 应用 Token（独立 Bitable）
            table_id: Bitable 表格 ID
            wiki_node_token: Wiki 节点 Token（Wiki 中的 Bitable）
        """
        self.app_id = app_id or os.getenv("FEISHU_APP_ID")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")
        self.app_token = app_token or os.getenv("FEISHU_BITABLE_APP_TOKEN")
        self.table_id = table_id or os.getenv("FEISHU_BITABLE_TABLE_ID")
        self.wiki_node_token = wiki_node_token or os.getenv("FEISHU_WIKI_NODE_TOKEN")

        self._tenant_access_token: Optional[str] = None
        self._token_expires: Optional[float] = None
        self._resolved_app_token: Optional[str] = None

    def _get_app_token(self) -> str:
        """获取 Bitable App Token（支持 Wiki 节点解析）"""
        if self._resolved_app_token:
            return self._resolved_app_token
        
        if self.app_token:
            self._resolved_app_token = self.app_token
            return self._resolved_app_token
        
        if self.wiki_node_token:
            token = self._get_tenant_access_token()
            headers = {"Authorization": f"Bearer {token}"}
            url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={self.wiki_node_token}"
            resp = requests.get(url, headers=headers, timeout=30)
            data = resp.json()
            
            if data.get("code") != 0:
                raise Exception(f"获取 Wiki 节点失败: {data}")
            
            node = data.get("data", {}).get("node", {})
            self._resolved_app_token = node.get("obj_token")
            if not self._resolved_app_token:
                raise Exception("Wiki 节点中未找到 Bitable App Token")
            
            logger.info(f"Wiki 节点解析成功: app_token={self._resolved_app_token}")
            return self._resolved_app_token
        
        raise Exception("未提供 app_token 或 wiki_node_token")

    def _get_tenant_access_token(self) -> str:
        """获取 tenant_access_token"""
        if self._tenant_access_token and self._token_expires and datetime.now() < self._token_expires:
            return self._tenant_access_token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = requests.post(
            url,
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=30,
        )
        data = resp.json()

        if data.get("code") != 0:
            raise Exception(f"获取 token 失败: {data}")

        self._tenant_access_token = data["tenant_access_token"]
        # token 有效期 2 小时，提前 10 分钟过期
        self._token_expires = datetime.now().timestamp() + data["expire"] - 600
        
        return self._tenant_access_token

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """发送请求"""
        token = self._get_tenant_access_token()
        app_token = self._get_app_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{self.table_id}{path}"
        resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        
        data = resp.json()
        if data.get("code") != 0:
            logger.error(f"Bitable API 错误: {data}")
            raise Exception(f"API 错误: {data.get('msg')}")
        
        return data.get("data", {})

    def add_record(self, fields: Dict[str, Any]) -> bool:
        """添加记录"""
        try:
            self._request("POST", "/records", json={"fields": fields})
            return True
        except Exception as e:
            logger.error(f"添加记录失败: {e}")
            return False

    def list_records(self, filter_str: Optional[str] = None, page_size: int = 500) -> List[Dict[str, Any]]:
        """获取记录列表"""
        records = []
        page_token = None
        
        while True:
            params = {"page_size": min(page_size, 500)}
            if page_token:
                params["page_token"] = page_token
            if filter_str:
                params["filter"] = filter_str

            data = self._request("GET", "/records", params=params)
            items = data.get("items", [])
            records.extend(items)
            
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")

        return records

    def store_article(self, article: Dict[str, Any]) -> bool:
        """存储单篇文章"""
        fields = {
            "标题": article.get("title", ""),
            "摘要": article.get("summary", "")[:500],
            "链接": {"link": article.get("link", ""), "text": "阅读原文"},
            "分类": article.get("category", ""),
            "日期": article.get("push_date", ""),
            "来源": article.get("source", ""),
            "重点推荐-大模型优化方向": article.get("featured_tag", ""),
        }
        return self.add_record(fields)

    def get_articles_by_date(self, date: str) -> List[Dict[str, Any]]:
        """按日期获取文章"""
        filter_str = f'CurrentValue.日期 = "{date}"'
        records = self.list_records(filter_str=filter_str)
        
        articles = []
        for record in records:
            fields = record.get("fields", {})
            link_field = fields.get("链接", {})
            link = link_field.get("link", "") if isinstance(link_field, dict) else ""
            
            articles.append({
                "id": record.get("record_id", ""),
                "title": fields.get("标题", ""),
                "summary": fields.get("摘要", ""),
                "link": link,
                "category": fields.get("分类", ""),
                "push_date": fields.get("日期", ""),
                "source": fields.get("来源", ""),
            })
        
        return articles
