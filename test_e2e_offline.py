# -*- coding: utf-8 -*-
"""
端到端离线集成测试（不依赖任何真实凭据）
=========================================
用 mock 替代外部依赖（DeepSeek API / SMTP / PushPlus / 飞书），
跑真实的 stock_mail_plugin.send_enhanced() 主路径，
验证：采集 -> 分析 -> 报告 -> 邮件 -> 推送 -> 落库 全链路衔接正确。

覆盖三个关键场景：
  1) 全链路（LLM 给"买入"，大盘正常 -> 护栏不干预）
  2) 护栏软化（大盘下挫 -2.5%，LLM 仍给"买入" -> 应软化为"观望"）
  3) 无 DeepSeek key 降级（analyzer 抛错 -> 回退规则报告，不崩）
"""
import sys, os, json, sqlite3
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
# 模拟"未配置 key"：置空串，让 analyzer 直接抛错（不联网），验证降级分支
config.DEEPSEEK_API_KEY = ""

import stock_mail_plugin
import analyzer
import notification_sender
import email_sender
import data_storage

PASS = 0
FAIL = 0


def check(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  \u2713 [PASS] " + msg)
    else:
        FAIL += 1
        print("  \u2717 [FAIL] " + msg)


def _mock_analysis(cautious=False):
    base = {
        "date": "2026-07-06",
        "source": "eastmoney",
        "fetched_at": "2026-07-07T08:00:00",
        "data_complete": True,
        "breadth": {"total": 5000, "up": 3000, "down": 1500, "flat": 500,
                    "up_limit": 80, "down_limit": 20},
        "north_flow": {"net_inflow": 35.5, "balance": 1800.0},
        "sectors": [{"rank": 1, "sector": "半导体", "chg": 3.5,
                     "leaders": [{"name": "中芯国际", "code": "688981", "chg": 5.2}]}],
        "indicators": [{"name": "上证指数", "price": 3200.5, "chg_pct": 1.2,
                        "macd": {"signal": "金叉"}, "kdj": {"signal": "多头"},
                        "rsi": {"signal": "偏强"}}],
        "news": [{"title": "央行降准利好市场", "url": "http://x", "source": "新浪财经",
                  "summary": "", "time": "", "impact": "利好"}],
    }
    if cautious:
        base["indices"] = [{"name": "上证指数", "code": "sh000001", "price": 3100.0,
                            "chg_pct": -2.5, "chg_val": -80.0, "high": 3150.0,
                            "low": 3080.0, "open": 3130.0, "volume": 0}]
    else:
        base["indices"] = [{"name": "上证指数", "code": "sh000001", "price": 3200.5,
                            "chg_pct": 1.2, "chg_val": 38.0, "high": 3210.0,
                            "low": 3180.0, "open": 3190.0, "volume": 0}]
    return base


MOCK_LLM_JSON = json.dumps({
    "decision": "买入", "score": 72, "confidence": 0.8,
    "summary": "市场情绪回暖，指数放量上行",
    "detail": "主要指数全线上涨，北向资金净流入，半导体板块领涨。",
    "risks": ["短期涨幅过大有回调风险"],
    "catalysts": ["央行降准利好流动性"],
    "watchlist": ["半导体", "券商"],
})


def _latest_snapshot():
    conn = sqlite3.connect(config.DATABASE_PATH)
    row = conn.execute(
        "SELECT id,llm_decision,llm_score,llm_confidence,source,data_complete "
        "FROM stock_market_snapshot ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row


def test_full_chain():
    print("\n=== 用例1: 全链路（mock 外部依赖，LLM=买入，大盘正常） ===")
    with mock.patch.object(stock_mail_plugin.AStockSpider,
                           'fetch_previous_trading_day_analysis',
                           return_value=_mock_analysis(False)), \
         mock.patch.object(stock_mail_plugin.MarketNewsSpider, 'fetch_news',
                           return_value=list(_mock_analysis(False)['news'])), \
         mock.patch.object(stock_mail_plugin.AStockSpider, 'fetch_sector_rankings',
                           return_value=list(_mock_analysis(False)['sectors'])), \
         mock.patch.object(analyzer, '_call_deepseek', return_value=MOCK_LLM_JSON), \
         mock.patch.object(notification_sender.WechatNotifier, 'send',
                           return_value=True) as m_wc, \
         mock.patch.object(notification_sender.FeishuNotifier, 'send_card',
                           return_value=True), \
         mock.patch.object(email_sender.EmailSender, '_create_smtp_connection',
                           lambda self: mock.MagicMock()), \
         mock.patch.object(stock_mail_plugin.db, 'get_latest_news', return_value=[]):
        ok = stock_mail_plugin.send_enhanced()

    check(ok is True, "send_enhanced() 返回 True（邮件发送成功）")
    check(m_wc.called, "PushPlus 微信推送被调用")
    if m_wc.called:
        a = m_wc.call_args
        template = a.args[2] if len(a.args) > 2 else None
        content = a.args[1]
        check(template == "markdown", "PushPlus 以 markdown 模板推送（非图片，避开图片看不清）")
        check(("\u4e70\u5165" in content) or ("\ud83d\udfe2" in content), "markdown 内容含决策信号")

    row = _latest_snapshot()
    check(row is not None, "A股快照已落库（stock_market_snapshot）")
    if row:
        check(row[1] == "\u4e70\u5165", "落库 llm_decision=买入（大盘正常，护栏未软化）")
        check(row[2] == 72, "落库 llm_score=72")
        check(abs(float(row[3]) - 0.8) < 0.01, "落库 llm_confidence=0.8")

    latest = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "market_report_latest.html")
    check(os.path.exists(latest), "报告 HTML 已生成（market_report_latest.html）")
    if os.path.exists(latest):
        html = open(latest, encoding="utf-8").read()
        check("\u4e70\u5165" in html, "报告含 AI 研判决策")
        check("\u53c2\u8003" in html, "报告含免责声明")


def test_guardrail_softening():
    print("\n=== 用例2: 护栏软化（大盘下挫 -2.5%，LLM 仍给买入 -> 应软化为观望） ===")
    with mock.patch.object(stock_mail_plugin.AStockSpider,
                           'fetch_previous_trading_day_analysis',
                           return_value=_mock_analysis(True)), \
         mock.patch.object(stock_mail_plugin.MarketNewsSpider, 'fetch_news',
                           return_value=[]), \
         mock.patch.object(stock_mail_plugin.AStockSpider, 'fetch_sector_rankings',
                           return_value=[]), \
         mock.patch.object(analyzer, '_call_deepseek', return_value=MOCK_LLM_JSON), \
         mock.patch.object(notification_sender.WechatNotifier, 'send',
                           return_value=True) as m_wc, \
         mock.patch.object(notification_sender.FeishuNotifier, 'send_card',
                           return_value=True), \
         mock.patch.object(email_sender.EmailSender, '_create_smtp_connection',
                           lambda self: mock.MagicMock()), \
         mock.patch.object(stock_mail_plugin.db, 'get_latest_news', return_value=[]):
        ok = stock_mail_plugin.send_enhanced()

    check(ok is True, "护栏场景 send_enhanced() 仍返回 True")
    row = _latest_snapshot()
    if row:
        check(row[1] == "\u89c2\u671b", "落库 llm_decision=观望（护栏将买入软化为观望）")
        check(float(row[3]) <= 0.5, "护栏场景置信度压低 <=0.5（实测 %.2f）" % float(row[3]))
    if m_wc.called:
        content = m_wc.call_args.args[1]
        check("\u89c2\u671b" in content, "微信 markdown 推送决策为观望")


def test_fallback_no_key():
    print("\n=== 用例3: 无 DeepSeek key 降级（analyzer 抛错 -> 规则报告不崩） ===")
    # 不 mock analyzer，让它用空 key 真实抛 RuntimeError -> 被捕获回退规则报告
    with mock.patch.object(stock_mail_plugin.AStockSpider,
                           'fetch_previous_trading_day_analysis',
                           return_value=_mock_analysis(False)), \
         mock.patch.object(stock_mail_plugin.MarketNewsSpider, 'fetch_news',
                           return_value=[]), \
         mock.patch.object(stock_mail_plugin.AStockSpider, 'fetch_sector_rankings',
                           return_value=[]), \
         mock.patch.object(notification_sender.WechatNotifier, 'send',
                           return_value=True), \
         mock.patch.object(notification_sender.FeishuNotifier, 'send_card',
                           return_value=True), \
         mock.patch.object(email_sender.EmailSender, '_create_smtp_connection',
                           lambda self: mock.MagicMock()), \
         mock.patch.object(stock_mail_plugin.db, 'get_latest_news', return_value=[]):
        ok = stock_mail_plugin.send_enhanced()
    check(ok is True, "无 key 时降级为规则报告，send_enhanced() 仍返回 True（不崩）")


if __name__ == "__main__":
    test_full_chain()
    test_guardrail_softening()
    test_fallback_no_key()
    print("\n========================================")
    print("端到端离线集成测试: PASS=%d  FAIL=%d" % (PASS, FAIL))
    print("========================================")
    sys.exit(1 if FAIL else 0)
