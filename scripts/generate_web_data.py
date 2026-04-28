"""
生成 Web 展示所需的 data.json
从飞书 Bitable 读取数据，生成为静态 JSON 文件。
"""

import traceback
import sys

try:
    import json
    import logging
    import os
    from pathlib import Path

    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    from storage.feishu_bitable import FeishuBitableStore

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    def generate_web_data():
        """生成 data.json"""
        logger.info("初始化 FeishuBitableStore...")
        logger.info(f"APP_ID: {os.getenv('FEISHU_APP_ID', '未设置')[:10]}...")
        logger.info(f"TABLE_ID: {os.getenv('FEISHU_BITABLE_TABLE_ID', '未设置')}")
        logger.info(f"WIKI_NODE: {os.getenv('FEISHU_WIKI_NODE_TOKEN', '未设置')[:10]}...")
        
        store = FeishuBitableStore()
        logger.info("正在从 Bitable 读取数据...")
        records = store.list_records(page_size=500)
        
        articles = []
        featured = []
        dates = set()
        categories = {}
        
        for record in records:
            fields = record.get("fields") or {}
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
            
            if article.get("featured_tag"):
                featured.append(article)
            
            cat = article["category"]
            categories[cat] = categories.get(cat, 0) + 1
        
        def _date_key(article):
            d = article.get("push_date", "")
            if d is None:
                return ""
            return str(d)
        
        articles.sort(key=_date_key, reverse=True)
        
        data = {
            "meta": {
                "total": len(articles),
                "dates": sorted([str(d) for d in dates if d], reverse=True),
                "categories": categories,
                "generated_at": __import__('datetime').datetime.now().isoformat(),
            },
            "articles": articles,
            "featured": featured,
        }
        
        output_path = PROJECT_ROOT / "data.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"data.json 已生成: {len(articles)} 篇文章")
        return output_path

    if __name__ == "__main__":
        generate_web_data()

except Exception:
    error_msg = traceback.format_exc()
    with open("error.log", "w", encoding="utf-8") as f:
        f.write(error_msg)
    raise
