"""
智驾AI日报 - 主入口脚本
串联 采集 -> 去重 -> 分类 -> 生成日报 -> 飞书推送 的完整流程。
"""

import io
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

# 修复 Windows 定时任务环境下 stdout 编码问题
if sys.stdout is None or not hasattr(sys.stdout, 'encoding') or sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None or not hasattr(sys.stderr, 'encoding') or sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8')

# 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from collectors.rss_collector import RSSCollector
from collectors.web_collector import WebCollector
from processors.dedup import Deduplicator
from processors.classifier import Classifier
from formatters.report import ReportFormatter
from notifiers.feishu import FeishuNotifier
from storage.vector_store import VectorStore
from storage.feishu_bitable import FeishuBitableStore


def setup_logging():
    """配置日志"""
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"daily_report_{datetime.now().strftime('%Y%m%d')}.log"

    handlers = [logging.FileHandler(str(log_file), encoding="utf-8")]
    # 仅在有可用控制台时添加 stdout handler
    try:
        if sys.stdout and sys.stdout.writable():
            handlers.append(logging.StreamHandler(sys.stdout))
    except Exception:
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def load_config() -> dict:
    """加载配置文件"""
    config_path = PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # 环境变量覆盖配置
    env_webhook = os.getenv("FEISHU_WEBHOOK")
    if env_webhook:
        config.setdefault("feishu", {})["webhook_url"] = env_webhook
    
    return config


def main():
    """主流程"""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("智驾AI日报 - 开始执行")
    logger.info("=" * 60)

    # 获取当前日期
    push_date = datetime.now().strftime("%Y-%m-%d")

    try:
        # 1. 加载配置
        config = load_config()
        logger.info("[配置] 加载成功")

        # 2. 采集新闻
        logger.info("[采集] 开始采集新闻...")
        all_articles = []
        success_sources = []
        failed_sources = []

        # RSS 采集
        rss_collector = RSSCollector(config)
        rss_articles = rss_collector.collect_all()
        all_articles.extend(rss_articles)
        logger.info(f"[采集] RSS 共采集 {len(rss_articles)} 篇")

        # 网页采集
        web_collector = WebCollector(config)
        web_articles = web_collector.collect_all()
        all_articles.extend(web_articles)
        logger.info(f"[采集] 网页共采集 {len(web_articles)} 篇")

        logger.info(f"[采集] 总计采集 {len(all_articles)} 篇文章")

        # 采集结果为 0 时记录警告但不直接退出
        if len(all_articles) == 0:
            logger.warning("[采集] 所有源均未获取到文章，可能是网络问题或源不可用")

        # 3. 去重与降噪
        logger.info("[处理] 开始去重降噪...")
        dedup = Deduplicator(similarity_threshold=0.65)
        unique_articles = dedup.deduplicate(all_articles)

        # 4. 分类
        logger.info("[处理] 开始内容分类...")
        classifier = Classifier(config)
        classified = classifier.classify(unique_articles)

        # 5. 判断是否有重要更新
        total_items = sum(len(v) for v in classified.values())
        formatter = ReportFormatter()
        notifier = FeishuNotifier(config)

        if total_items == 0:
            logger.info("[结果] 今日无重要更新（采集到 %d 篇原始文章，分类后为 0 篇）", len(all_articles))
            message = formatter.format_no_update_message()
        else:
            logger.info(f"[结果] 共筛选出 {total_items} 篇相关资讯")

            # 6. 生成机会洞察
            insights = classifier.generate_insights(classified)

            # 7. 生成日报
            logger.info("[生成] 开始生成日报...")

            # 打印纯文本版本到日志
            text_report = formatter.format_text(classified, insights)
            logger.info(f"[日报预览]\n{text_report}")

            # 生成飞书富文本版本
            message = formatter.format_feishu_post(classified, insights)

        # 8. 推送到飞书
        logger.info("[推送] 发送到飞书...")
        success = notifier.send(message)

        if success:
            logger.info("[完成] 日报推送成功！（共 %d 篇资讯）", total_items)

            # 9. 存入向量数据库（本地备份）
            if total_items > 0:
                try:
                    vector_store = VectorStore()
                    stored = vector_store.store_articles(classified)
                    stats = vector_store.get_stats()
                    logger.info(
                        f"[向量库] 历史累计 {stats['total']} 条记录，"
                        f"覆盖 {len(stats['dates'])} 天"
                    )
                except Exception as e:
                    logger.warning(f"[向量库] 存储失败（不影响推送）: {e}")

            # 10. 存入飞书 Bitable（云端数据库）
            if total_items > 0:
                try:
                    bitable = FeishuBitableStore()
                    stored_count = 0
                    for category, articles in classified.items():
                        for article in articles:
                            article["push_date"] = push_date
                            article["category"] = article.get("display_category", category)
                            if bitable.store_article(article):
                                stored_count += 1
                    logger.info(f"[Bitable] 成功存储 {stored_count} 篇文章到飞书")
                except Exception as e:
                    logger.warning(f"[Bitable] 存储失败（不影响推送）: {e}")
        else:
            logger.warning("[完成] 日报推送失败，请检查 Webhook 配置")

    except Exception as e:
        logger.error(f"[错误] 执行异常: {e}", exc_info=True)
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("智驾AI日报 - 执行完毕")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
