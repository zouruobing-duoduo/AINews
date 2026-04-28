"""
NewsQoder 可视化 Web 界面
分类展示历史推送消息，支持搜索和直达原网址。
"""

import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from storage.vector_store import VectorStore
    vector_store = VectorStore()
except Exception as e:
    print(f"[警告] 向量数据库加载失败: {e}")
    vector_store = None

app = Flask(__name__)

# 分类名称映射
CATEGORY_NAMES = {
    "ad_industry": "智能驾驶产业",
    "ai_industry": "AI产业",
    "ad_tech": "智能驾驶技术",
    "ai_tech": "AI技术",
    "policy": "政策法规",
    "智能驾驶产业": "智能驾驶产业",
    "AI产业": "AI产业",
    "智能驾驶技术": "智能驾驶技术",
    "AI技术": "AI技术",
    "政策法规": "政策法规",
}


@app.route("/")
def index():
    """主页"""
    return render_template("index.html")


@app.route("/api/articles")
def get_articles():
    """获取文章列表（支持筛选和搜索）"""
    try:
        # 查询参数
        category = request.args.get("category", "")
        date = request.args.get("date", "")
        query = request.args.get("q", "")
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))

        # 检查向量库是否可用
        if vector_store is None:
            return jsonify({"articles": [], "total": 0, "page": page, "per_page": per_page})

        # 从向量库查询
        store = vector_store

        if query:
            # 搜索模式
            results = store.search(query, n_results=100, category=category or None)
        elif date:
            # 按日期查询
            results = store.get_by_date(date)
            if category:
                results = [r for r in results if r.get("category") == category]
        else:
            # 获取所有（默认最近7天）
            from datetime import datetime, timedelta

            date_to = datetime.now().strftime("%Y-%m-%d")
            date_from = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            results = store.search(
                "", n_results=1000, category=category or None, date_from=date_from, date_to=date_to
            )

        # 按日期倒序排序
        results.sort(key=lambda x: x.get("push_date", ""), reverse=True)

        # 分页
        total = len(results)
        start = (page - 1) * per_page
        end = start + per_page
        paginated = results[start:end]

        # 格式化响应
        articles = []
        for item in paginated:
            articles.append({
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "source": item.get("source", ""),
                "link": item.get("link", ""),
                "category": item.get("category", ""),
                "push_date": item.get("push_date", ""),
                "published": item.get("published", ""),
            })

        return jsonify({
            "success": True,
            "data": articles,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/stats")
def get_stats():
    """获取统计数据"""
    try:
        if vector_store is None:
            return jsonify({
                "success": True,
                "data": {"total": 0, "dates": [], "categories": {}}
            })
        store = vector_store
        stats = store.get_stats()

        # 格式化分类名称
        categories = {}
        for cat, count in stats.get("categories", {}).items():
            display_name = CATEGORY_NAMES.get(cat, cat)
            categories[display_name] = count

        return jsonify({
            "success": True,
            "data": {
                "total": stats.get("total", 0),
                "dates": stats.get("dates", []),
                "categories": categories,
            },
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dates")
def get_dates():
    """获取所有有数据的日期"""
    try:
        if vector_store is None:
            return jsonify({"success": True, "data": []})
        store = vector_store
        stats = store.get_stats()
        return jsonify({"success": True, "data": stats.get("dates", [])})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    print("=" * 50)
    print("NewsQoder Web 界面启动")
    print("访问地址: http://localhost:5000")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)
