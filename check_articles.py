"""检查数据库中的文章"""
import sys
sys.path.insert(0, 'e:/GitCode/NewsQoder')
from storage.vector_store import VectorStore

store = VectorStore()

# 获取统计信息
stats = store.get_stats()
print(f"总文章数: {stats['total']}")
print(f"日期列表: {stats['dates']}")
print(f"\n分类统计: {stats['categories']}")

# 检查上周六和周日的文章
sat_articles = store.get_by_date("2026-04-18")
sun_articles = store.get_by_date("2026-04-19")

print(f"\n上周六(2026-04-18)文章数: {len(sat_articles)}")
for a in sat_articles[:3]:
    print(f"  - {a['title'][:50]}...")

print(f"\n上周日(2026-04-19)文章数: {len(sun_articles)}")
for a in sun_articles[:3]:
    print(f"  - {a['title'][:50]}...")
