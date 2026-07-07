"""
盘前自动运行入口（供 Windows 任务计划 / cron 调用）。

流程：
  1. 判断今天是否为 A股交易日（trading_day）
  2. 是交易日 -> 调用 stock_mail_plugin.send_enhanced() 生成并推送完整报告
  3. 非交易日 -> 直接退出（不推送，避免周末/节假日空报告）

设计原则：
  - 进程跑完即退，不常驻（契合自托管/零成本/本地）；
  - 失败有日志且不抛半成品，返回非 0 退出码供调度器告警；
  - 真实数据缺失时由下游模块负责降级/标注，本入口不编造。
"""
import sys
import logging
from datetime import date

import trading_day
import stock_mail_plugin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("run_daily")


def main() -> int:
    today = date.today()
    if not trading_day.is_trading_day(today):
        logger.info("非交易日（%s），跳过盘前报告。", today.isoformat())
        return 0

    logger.info("交易日 %s，开始生成盘前报告……", today.isoformat())
    try:
        ok = stock_mail_plugin.send_enhanced()
    except Exception as e:  # noqa: BLE001 - 顶层兜底，避免半成品推送
        logger.exception("盘前报告生成失败：%s", e)
        return 2

    if not ok:
        logger.warning("盘前报告未发送（无数据或推送未配置）。")
        return 1
    logger.info("盘前报告已生成并推送。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
