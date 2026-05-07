"""
内容分类模块
基于关键词匹配将资讯分为：产业动态、技术进展、政策法规，并按相关性排序。
"""

import logging
from collections import Counter
from typing import List, Dict, Any, Tuple

from collectors.rss_collector import CORE_DOMAIN_KEYWORDS

logger = logging.getLogger(__name__)

# 细分类别关键词映射
CATEGORY_KEYWORDS = {
    "ad_industry": {
        "name": "智能驾驶产业",
        "keywords": [
            "自动驾驶", "智能驾驶", "智驾", "无人驾驶", "Robotaxi",
            "L2", "L3", "L4", "NOA", "城市领航", "辅助驾驶",
            "融资", "收购", "合作", "上市", "量产", "交付",
            "小鹏", "理想", "蔚来", "华为", "小米汽车", "特斯拉", "FSD",
            "小马智行", "文远知行", "百度Apollo", "Waymo",
            "商业化", "运营", "落地", "订单", "销量", "渗透率",
        ],
    },
    "ai_industry": {
        "name": "AI产业",
        "keywords": [
            "AI", "人工智能", "大模型", "LLM", "GPT", "AGI", "通用人工智能",
            "OpenAI", "DeepSeek", "Anthropic", "Claude", "Gemini", "Grok",
            "具身智能", "人形机器人", "机器人", "机械臂",
            "AI硬件", "AI相机", "AI摄像头", "跟踪",
            "OBSBOT", "寻影", "大疆", "DJI", "影石", "Insta360",
            "融资", "收购", "上市", "估值", "IPO",
            "商业化", "产品发布", "用户增长", "市场份额",
            "芯片", "GPU", "NPU", "算力", "云服务", "AI芯片",
        ],
    },
    "ad_tech": {
        "name": "智能驾驶技术",
        "keywords": [
            "端到端", "VLA", "世界模型", "BEV", "Transformer",
            "感知", "规划", "决策", "控制", "定位", "建图",
            "激光雷达", "毫米波雷达", "摄像头", "传感器",
            "数据闭环", "仿真", "OTA", "影子模式",
            "NOA", "城市领航", "自动泊车", "智能座舱",
        ],
    },
    "ai_tech": {
        "name": "AI技术",
        "keywords": [
            "多模态", "智能体", "Agent", "RAG", "提示工程", "人机协同",
            "Transformer", "注意力机制", "强化学习", "RLHF",
            "训练", "推理", "微调", "对齐", "蒸馏", "MoE", "混合专家",
            "开源", "论文", "SOTA", "基准测试",
            "生成式AI", "AIGC", "文生图", "文生视频", "文生3D",
            "量子计算", "量子", "6G", "通信", "神经网络", "深度学习",
            "脑科学", "认知科学", "神经科学", "类脑计算", "神经可塑性",
            "认知计算", "脑机接口", "BCI", "NeuroAI",
        ],
    },
}


class Classifier:
    """内容分类器"""

    def __init__(self, config: Dict[str, Any]):
        self.max_items = config.get("max_items_per_category", 8)
        self.filter_keywords = config.get("filter_keywords", {})
        self.high_priority = self.filter_keywords.get("high_priority", [])
        self.medium_priority = self.filter_keywords.get("medium_priority", [])

    def classify(
        self, articles: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        将文章分类到各板块，并按相关性排序。

        Returns:
            {
                "industry": [...],    # 产业动态
                "technology": [...],  # 技术进展
                "policy": [...],      # 政策法规
            }
        """
        classified = {key: [] for key in CATEGORY_KEYWORDS}

        for article in articles:
            scores = self._calculate_category_scores(article)
            # 分配到得分最高的分类
            best_category = max(scores, key=scores.get)
            if scores[best_category] > 0:
                article["category_score"] = scores[best_category]
                article["display_category"] = CATEGORY_KEYWORDS[best_category]["name"]
                classified[best_category].append(article)
            else:
                # 无明确分类且与智驾/AI无关，直接丢弃
                logger.debug(f"[分类] 丢弃无关文章: {article.get('title', '')}")
                continue

        # 各分类按综合评分排序并截取
        for key in classified:
            classified[key].sort(
                key=lambda x: (
                    self._priority_score(x),
                    x.get("category_score", 0),
                    x.get("relevance_score", 0),
                ),
                reverse=True,
            )
            classified[key] = classified[key][: self.max_items]

        total = sum(len(v) for v in classified.values())
        logger.info(
            f"[分类] 智能驾驶产业: {len(classified['ad_industry'])}, "
            f"AI产业: {len(classified['ai_industry'])}, "
            f"智能驾驶技术: {len(classified['ad_tech'])}, "
            f"AI技术: {len(classified['ai_tech'])} (共 {total} 篇)"
        )

        return classified

    def _calculate_category_scores(self, article: Dict[str, Any]) -> Dict[str, int]:
        """计算文章在各分类下的关键词匹配得分，标题权重更高"""
        title = article.get("title", "").lower()
        summary = article.get("summary", "").lower()
        
        scores = {}
        for cat_key, cat_info in CATEGORY_KEYWORDS.items():
            # 标题匹配权重 3 倍，摘要匹配权重 1 倍
            title_score = sum(3 for kw in cat_info["keywords"] if kw.lower() in title)
            summary_score = sum(1 for kw in cat_info["keywords"] if kw.lower() in summary)
            scores[cat_key] = title_score + summary_score
        
        # 智能分类纠偏：根据标题特征词强制调整
        # AI 类特征词（消费级AI硬件、直播设备等）
        ai_signals = ["ai ", "ai产业", "人工智能", "大模型", "llm", "gpt", "openai", "claude", "deepseek", "agi", "通用人工智能", "具身智能", "人形机器人", "量子计算", "6g", "人机协同", "obsbot", "寻影", "影石", "insta360", "脑科学", "认知科学", "神经科学", "类脑计算", "neuroai"]
        # 智驾类特征词（必须同时排除消费级产品）
        ad_signals = ["自动驾驶", "智能驾驶", "智驾", "无人驾驶", "robotaxi", "fsd", "noa", "城市领航", "车载", "车规", "激光雷达", "毫米波", "域控制器"]
        
        has_ai_signal = any(s in title for s in ai_signals)
        has_ad_signal = any(s in title for s in ad_signals)
        
        if has_ai_signal and not has_ad_signal:
            # 纯 AI 文章，降低智驾类得分
            scores["ad_industry"] = scores.get("ad_industry", 0) // 3
            scores["ad_tech"] = scores.get("ad_tech", 0) // 3
        elif has_ad_signal and not has_ai_signal:
            # 纯智驾文章，降低 AI 类得分
            scores["ai_industry"] = scores.get("ai_industry", 0) // 3
            scores["ai_tech"] = scores.get("ai_tech", 0) // 3
        
        return scores

    def _priority_score(self, article: Dict[str, Any]) -> int:
        """根据高/中优先级关键词计算优先级得分"""
        text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
        score = 0
        for kw in self.high_priority:
            if kw.lower() in text:
                score += 3
        for kw in self.medium_priority:
            if kw.lower() in text:
                score += 1
        return score

    def generate_insights(
        self, classified: Dict[str, List[Dict[str, Any]]]
    ) -> List[str]:
        """基于当日采集内容生成机会洞察"""
        # 统计所有文章中出现的高优关键词频率
        all_articles = []
        for articles in classified.values():
            all_articles.extend(articles)

        if not all_articles:
            return ["今日暂无明显趋势信号。"]

        keyword_counter = Counter()
        for article in all_articles:
            text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
            for kw in self.high_priority + self.medium_priority:
                if kw.lower() in text:
                    keyword_counter[kw] += 1

        # 取 Top 热词生成洞察
        insights = []
        top_keywords = keyword_counter.most_common(5)

        if top_keywords:
            trend_parts = []
            for kw, count in top_keywords[:3]:
                trend_parts.append(f"「{kw}」({count}次提及)")
            insights.append(
                f"今日热点关键词: {', '.join(trend_parts)}，"
                f"建议持续关注相关技术路线与产业动向。"
            )

        # 技术类洞察（智能驾驶技术 + AI技术）
        tech_articles = classified.get("ad_tech", []) + classified.get("ai_tech", [])
        if len(tech_articles) >= 3:
            tech_keywords = set()
            for a in tech_articles:
                tech_keywords.update(a.get("matched_keywords", []))
            if tech_keywords:
                insights.append(
                    f"技术路线方面，{'、'.join(list(tech_keywords)[:4])}等方向进展密集，值得深入跟踪。"
                )

        if not insights:
            insights.append("今日资讯分布均匀，未发现集中爆发的趋势信号。")

        return insights[:3]

    def select_featured(
        self,
        classified: Dict[str, List[Dict[str, Any]]],
        max_total: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        从各分类中选取得分最高的文章作为重点推荐。
        每个分类最多选 1 篇，总共不超过 max_total 篇。
        """
        featured = []
        for cat_key, articles in classified.items():
            if not articles:
                continue
            # 按综合优先级得分排序
            sorted_articles = sorted(
                articles,
                key=lambda x: (
                    self._priority_score(x),
                    x.get("category_score", 0),
                ),
                reverse=True,
            )
            # 取该分类得分最高的一篇
            best = sorted_articles[0]
            featured.append({
                "title": best.get("title", ""),
                "summary": best.get("summary", "")[:300],
                "link": best.get("link", ""),
                "source": best.get("source", ""),
                "category": best.get("display_category", CATEGORY_KEYWORDS.get(cat_key, {}).get("name", cat_key)),
                "category_tag": "大模型优化方向",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "sort_order": len(featured),
            })
        # 按排序截取
        featured.sort(key=lambda x: x["sort_order"])
        return featured[:max_total]
