"""
生成 Web 展示所需的 data.json
从飞书 Bitable 读取数据，生成为静态 JSON 文件。
"""

import json
import logging
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from storage.feishu_bitable import FeishuBitableStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_web_data():
    """生成 data.json"""
    store = FeishuBitableStore()
    
    logger.info("正在从 Bitable 读取数据...")
    
    # 获取所有文章（限制最近 30 天）
    records = store.list_records(page_size=500)
    
    articles = []
    featured = []
    dates = set()
    categories = {}
    
    for record in records:
        fields = record.get("fields", {})
        link_field = fields.get("链接", {})
        link = link_field.get("link", "") if isinstance(link_field, dict) else ""
        
        article = {
            "id": record.get("record_id", ""),
            "title": fields.get("标题", ""),
            "summary": fields.get("摘要", ""),
            "link": link,
            "category": fields.get("分类", ""),
            "push_date": fields.get("日期", ""),
            "source": fields.get("来源", ""),
            "featured_tag": fields.get("重点推荐-大模型优化方向", ""),
        }
        
        articles.append(article)
        dates.add(article["push_date"])
        
        # 如果标记为重点推荐，加入 featured 列表
        if article.get("featured_tag"):
            featured.append(article)
        
        # 统计分类
        cat = article["category"]
        categories[cat] = categories.get(cat, 0) + 1
    
    # 按日期倒序排序
    articles.sort(key=lambda x: x.get("push_date", ""), reverse=True)
    
    # 构建 data.json
    data = {
        "meta": {
            "total": len(articles),
            "dates": sorted(list(dates), reverse=True),
            "categories": categories,
            "generated_at": __import__('datetime').datetime.now().isoformat(),
        },
        "articles": articles,
        "featured": featured,  # 重点推荐可后续从 Bitable 另一个表读取
    }
    
    # 保存到项目根目录
    output_path = PROJECT_ROOT / "data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"data.json 已生成: {len(articles)} 篇文章")
    return output_path


if __name__ == "__main__":
    generate_web_data()
