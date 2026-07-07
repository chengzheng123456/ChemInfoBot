# Phase-2 验证脚本（不依赖真实 DeepSeek key，用 stub 替代 _call_deepseek）
# 覆盖：guardrail 软化、context 不编造、PushPlus markdown、LLM 报告含免责、快照落库 LLM 结论。
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyzer
import market_report
import notification_sender
from data_storage import db

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("PASS - " + name)
    else:
        FAIL += 1
        print("FAIL - " + name)


def make_analysis(indices_chg=0.5, data_complete=True):
    return {
        "date": "2026-07-06",
        "source": "eastmoney",
        "fetched_at": "2026-07-07T08:30:00",
        "data_complete": data_complete,
        "indices": [
            {"name": "上证指数", "code": "sh000001", "price": 3200.0, "chg_pct": indices_chg,
             "chg_val": 16.0, "high": 3210, "low": 3190, "open": 3195, "volume": 0},
            {"name": "深证成指", "code": "sz399001", "price": 10100.0, "chg_pct": 0.8,
             "chg_val": 80.0, "high": 10150, "low": 10050, "open": 10080, "volume": 0},
        ],
        "breadth": {"total": 5000, "up": 2600, "down": 2200, "flat": 200,
                    "up_limit": 50, "down_limit": 30},
        "north_flow": {"net_inflow": 25.5, "balance": 1800.0},
        "sectors": [{"rank": 1, "sector": "半导体", "chg": 3.2,
                     "leaders": [{"name": "中芯国际", "code": "688981", "chg": 5.1}]}],
        "indicators": [{"name": "上证指数", "price": 3200.0, "chg_pct": 0.5,
                        "macd": {"dif": 10, "dea": 8, "macd": 4, "signal": "金叉"},
                        "kdj": {"k": 40, "d": 38, "j": 44, "signal": "中性"},
                        "rsi": {"rsi6": 55, "rsi12": 52, "rsi24": 50, "signal": "偏强"}}],
        "news": [{"title": "半导体板块利好政策出台", "url": "http://x", "source": "新浪财经",
                  "summary": "", "time": "", "impact": "利好"}],
    }


FAKE_LLM = {
    "decision": "买入", "score": 72, "confidence": 0.8,
    "summary": "市场偏强，半导体领涨", "detail": "主要指数上涨，半导体板块领涨。",
    "risks": ["短期涨幅过大"], "catalysts": ["政策利好"], "watchlist": ["半导体"],
}


def main():
    # stub：不真调 API
    analyzer._call_deepseek = lambda *a, **k: json.dumps(FAKE_LLM)

    # ---- 1. 正常市场：guardrail 不改变“买入” ----
    a_normal = make_analysis(indices_chg=0.5)
    r1 = analyzer.apply_guardrail(dict(FAKE_LLM), a_normal)
    check("P2 normal: decision stays 买入", r1["decision"] == "买入")
    check("P2 normal: confidence preserved (0.8)", r1["confidence"] == 0.8)
    check("P2 normal: disclaimer added", "不构成投资建议" in r1.get("disclaimer", ""))
    check("P2 normal: source traced", r1.get("source") == "eastmoney")
    check("P2 normal: fetched_at traced", r1.get("fetched_at") == "2026-07-07T08:30:00")

    # ---- 2. 大盘偏弱：买入 软化为 观望 ----
    a_cautious = make_analysis(indices_chg=-2.0)  # 上证跌 2%
    r2 = analyzer.apply_guardrail(dict(FAKE_LLM), a_cautious)
    check("P2 cautious: 买入 softened to 观望", r2["decision"] == "观望")
    check("P2 cautious: guardrail_note present", "软化为" in r2.get("guardrail_note", ""))
    check("P2 cautious: confidence capped <=0.5", r2["confidence"] <= 0.5)

    # ---- 3. 数据不完整：买入 降级为 持有 + 置信度压低 ----
    a_incomplete = make_analysis(indices_chg=0.5, data_complete=False)
    r3 = analyzer.apply_guardrail(dict(FAKE_LLM), a_incomplete)
    check("P2 incomplete: 买入 downgraded to 持有", r3["decision"] == "持有")
    check("P2 incomplete: confidence <= 0.4", r3["confidence"] <= 0.4)

    # ---- 4. context pack 不编造（缺失字段标注“未获取”） ----
    a_missing = {"indices": None, "breadth": None, "north_flow": None,
                 "sectors": None, "indicators": None, "news": None,
                 "source": "eastmoney", "fetched_at": "t", "data_complete": False}
    ctx = analyzer.build_context_pack(a_missing)
    check("P2 context: missing indices labeled 未获取", "【主要指数】未获取" in ctx)
    check("P2 context: missing breadth labeled 未获取", "【涨跌分布】未获取" in ctx)
    check("P2 context: no fabricated number for 上证", "上证指数" not in ctx.split("【主要指数】")[1].split("【")[0])

    # ---- 5. PushPlus markdown 渲染 ----
    md = notification_sender.format_pushplus_markdown(r1, a_normal)
    check("P2 md: contains decision", "买入" in md)
    check("P2 md: contains 研判分", "研判分" in md)
    check("P2 md: contains disclaimer", "不构成投资建议" in md)
    md_cautious = notification_sender.format_pushplus_markdown(r2, a_cautious)
    check("P2 md: guardrail note shown when present", "护栏提示" in md_cautious)

    # ---- 6. LLM 报告 HTML 含研判卡 + 免责 + 真实数据 ----
    html = market_report.generate_llm_report(a_normal, r1)
    check("P2 report: AI 研判 card present", "AI 盘前研判" in html)
    check("P2 report: disclaimer present", "不构成投资建议" in html)
    check("P2 report: real index name present", "上证指数" in html)
    check("P2 report: decision badge present", "买入" in html)

    # ---- 7. 快照落库 LLM 结论 ----
    snap_id = db.save_market_snapshot(a_normal, r1)
    check("P2 snapshot: id > 0", snap_id > 0)
    with db._get_connection() as conn:
        row = conn.execute(
            "SELECT llm_decision, llm_score, llm_confidence FROM stock_market_snapshot WHERE id=?",
            (snap_id,)).fetchone()
    check("P2 snapshot: llm_decision stored", row["llm_decision"] == "买入")
    check("P2 snapshot: llm_score stored", row["llm_score"] == 72)
    check("P2 snapshot: llm_confidence stored", abs(row["llm_confidence"] - 0.8) < 1e-6)

    print("\n==== RESULT: %d PASS / %d FAIL ====" % (PASS, FAIL))
    return FAIL == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
