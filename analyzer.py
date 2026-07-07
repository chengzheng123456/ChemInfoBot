# Phase-2 LLM analysis layer (DeepSeek) + deterministic guardrail
# 设计原则：自托管采集层（阶段一）之上叠加云端 LLM 研判；
#           护栏为确定性逻辑，不依赖模型强推理，防过度承诺/编造误导。
import logging
import json
import requests

import config

logger = logging.getLogger(__name__)

DEEPSEEK_API = "https://api.deepseek.com/chat/completions"

SYSTEM_PROMPT = """你是一名严谨的 A 股盘前/盘后分析助手。你将收到一份由爬虫抓取的真实市场数据快照。
任务：仅基于提供的数据，给出结构化研判。

硬性约束：
1. 只基于提供的数据分析，绝对不得编造数据中不存在的数字、新闻或个股。
2. 数据标注“未获取”的字段，你必须写“数据缺失”，不得臆测。
3. 输出严格 JSON，字段如下：
{
  "decision": "买入" | "观望" | "持有" | "卖出",
  "score": 0-100 的整数（综合研判分，越高越偏多），
  "confidence": 0-1 之间的小数（你对本次判断的把握），
  "summary": "一句话市场总结（≤40字）",
  "detail": "2-4 句分析（基于真实数据，不含虚构）",
  "risks": ["不超过3条风险点（基于真实数据）"],
  "catalysts": ["不超过3条催化/利好（基于真实数据，无则空数组）"],
  "watchlist": ["值得关注的板块或方向"]
}
4. 你不是投资顾问，不提供具体买卖价位；若被追问点位需声明不确定性。
5. 这是研究辅助，不构成投资建议。
"""


def build_context_pack(analysis_data):
    """把阶段一采集的真实数据装配成给 LLM 的上下文（不含任何编造）。"""
    L = []
    L.append("【数据抓取时间】" + str(analysis_data.get("fetched_at", "未知")))
    L.append("【数据源】" + str(analysis_data.get("source", "未知")))
    if not analysis_data.get("data_complete", True):
        L.append("【注意】部分数据获取失败，以下字段可能缺失，分析时须如实标注。")

    idx = analysis_data.get("indices")
    if idx:
        L.append("【主要指数】")
        for x in idx[:8]:
            L.append("- %s: %.2f (%+.2f%%)，今开%.2f 高%.2f 低%.2f" % (
                x.get("name", ""), x.get("price", 0), x.get("chg_pct", 0),
                x.get("open", 0), x.get("high", 0), x.get("low", 0)))
    else:
        L.append("【主要指数】未获取")

    brd = analysis_data.get("breadth")
    if brd:
        L.append("【涨跌分布】上涨%d 下跌%d 平盘%d 涨停%d 跌停%d 共%d只" % (
            brd.get("up", 0), brd.get("down", 0), brd.get("flat", 0),
            brd.get("up_limit", 0), brd.get("down_limit", 0), brd.get("total", 0)))
    else:
        L.append("【涨跌分布】未获取")

    nf = analysis_data.get("north_flow")
    if nf:
        L.append("【北向资金】净流入 %+.2f 亿" % nf.get("net_inflow", 0))
    else:
        L.append("【北向资金】未获取")

    secs = analysis_data.get("sectors")
    if secs:
        L.append("【行业板块TOP】")
        for s in secs[:5]:
            ld = ",".join([l.get("name", "") for l in s.get("leaders", [])[:3]])
            L.append("- %s %+.2f%%（领涨:%s）" % (s.get("sector", ""), s.get("chg", 0), ld))
    else:
        L.append("【行业板块】未获取")

    inds = analysis_data.get("indicators")
    if inds:
        L.append("【技术指标】")
        for i in inds[:4]:
            macd = i.get("macd", {})
            kdj = i.get("kdj", {})
            rsi = i.get("rsi", {})
            L.append("- %s MACD:%s KDJ:%s RSI:%s" % (
                i.get("name", ""), macd.get("signal", "-"),
                kdj.get("signal", "-"), rsi.get("signal", "-")))
    else:
        L.append("【技术指标】未获取")

    news = analysis_data.get("news")
    if news:
        L.append("【市场要闻】")
        for n in news[:8]:
            L.append("- [%s] %s" % (n.get("impact", ""), n.get("title", "")))
    else:
        L.append("【市场要闻】未获取")

    return "\n".join(L)


def _call_deepseek(system_prompt, user_prompt, model=None, temperature=0.3):
    """调用 DeepSeek 兼容 OpenAI 的 chat/completions 接口。"""
    api_key = getattr(config, "DEEPSEEK_API_KEY", "") or ""
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置（config.DEEPSEEK_API_KEY）")
    model = model or getattr(config, "DEEPSEEK_MODEL", "deepseek-chat")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    try:
        r = requests.post(
            DEEPSEEK_API,
            headers={"Authorization": "Bearer " + api_key,
                     "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error("DeepSeek API call failed: %s", e)
        raise


def _is_market_cautious(analysis_data):
    """确定性判定大盘环境是否偏弱（guardrail 用，不依赖 LLM）。"""
    idx = analysis_data.get("indices") or []
    brd = analysis_data.get("breadth") or {}
    for x in idx:
        if x.get("chg_pct", 0) <= -1.5:
            return True
    up = brd.get("up", 0)
    down = brd.get("down", 0)
    if up and down and down > up * 1.5:
        return True
    nf = analysis_data.get("north_flow") or {}
    if nf and nf.get("net_inflow", 0) <= -50:
        return True
    return False


def apply_guardrail(result, analysis_data):
    """在 LLM 输出之上叠加确定性护栏，防过度承诺/编造误导。"""
    result = dict(result)
    cautious = _is_market_cautious(analysis_data)
    notes = []

    decision = result.get("decision", "观望")
    # 1. 大盘偏弱时，把“买入”软化为“观望”
    if cautious and decision == "买入":
        decision = "观望"
        notes.append("大盘环境偏弱（指数下挫/涨跌比恶化/北向大幅流出），已将'买入'软化为'观望'")
    # 2. 数据不完整时，禁止“买入”，置信度压低
    if not analysis_data.get("data_complete", True):
        if decision == "买入":
            decision = "持有"
        notes.append("部分市场数据缺失，结论仅供参考，已下调确定性")
        result["confidence"] = round(min(float(result.get("confidence", 0.5)), 0.4), 2)

    # 3. 置信度上限约束（防 LLM 过度自信）
    conf = float(result.get("confidence", 0.5))
    if cautious:
        conf = min(conf, 0.5)
    result["confidence"] = round(min(conf, 0.85), 2)
    result["decision"] = decision
    if notes:
        result["guardrail_note"] = "；".join(notes)

    # 4. 强制免责声明
    result["disclaimer"] = "AI 生成，基于真实行情数据，仅供参考，不构成投资建议"
    # 5. 溯源透传
    result["source"] = analysis_data.get("source")
    result["fetched_at"] = analysis_data.get("fetched_at")
    result["data_complete"] = analysis_data.get("data_complete", True)
    return result


def analyze(analysis_data, verify=False):
    """主入口：装配上下文 -> 调 DeepSeek -> 套护栏 -> 可选复核。"""
    ctx = build_context_pack(analysis_data)
    raw = _call_deepseek(SYSTEM_PROMPT, ctx)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("DeepSeek returned non-JSON: %s", raw[:200])
        raise ValueError("LLM 输出解析失败")
    result = apply_guardrail(result, analysis_data)
    # 可选：用 deepseek-reasoner 对关键决策做二次复核
    if verify and getattr(config, "DEEPSEEK_VERIFY_MODEL", ""):
        try:
            vp = "复核以下研判是否稳妥，只回答'认可'或指出明显问题（≤50字）：\n" + \
                 json.dumps(result, ensure_ascii=False)
            vr = _call_deepseek("你是严谨的量化复核员。", vp,
                                model=config.DEEPSEEK_VERIFY_MODEL, temperature=0.1)
            result["verify_note"] = vr.strip()[:120]
        except Exception as e:
            logger.warning("Verify call failed: %s", e)
    return result
