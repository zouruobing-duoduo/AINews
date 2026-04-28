"""初始化重点推荐数据"""
import sys
sys.path.insert(0, 'e:/GitCode/NewsQoder')
from storage.vector_store import VectorStore

store = VectorStore()

# 添加重点推荐
featured_articles = [
    {
        'title': '认知科学与学习机制：近五年脑科学前沿进展报告',
        'summary': '本文系统梳理了近五年来脑科学在认知功能和学习机制方面的突破性研究，涵盖注意力、记忆、决策等认知过程，以及神经可塑性与深度学习的关系。',
        'link': 'https://blog.csdn.net/shizheng_Li/article/details/146338734',
        'category_tag': '大模型优化方向',
        'source': 'CSDN',
        'date': '2025年3月',
        'sort_order': 1
    },
    {
        'title': '赛博脑白金，能治好AI的失忆症吗？',
        'summary': '探讨AI长文本记忆与上下文理解的技术挑战，分析当前大模型在持续学习和知识保持方面的局限性，以及可能的解决方案和技术路线。',
        'link': 'https://www.huxiu.com/article/4313930.html',
        'category_tag': '大模型优化方向',
        'source': '虎嗅',
        'date': '2025年',
        'sort_order': 2
    }
]

for article in featured_articles:
    store.add_featured(article)
    print(f"已添加: {article['title']}")

print(f"\n重点推荐总数: {len(store.get_featured())}")
