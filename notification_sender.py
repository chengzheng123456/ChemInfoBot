# 多通道推送模块（飞书 + 微信/PushPlus）
# 阶段二：微信侧优先推送 markdown 文字报告（清晰可读，不依赖图片）；
#         新增 format_pushplus_markdown 生成 AI 研判的纯文字版。
import logging
import json
import requests
import hashlib
import base64
import hmac
import time
from datetime import datetime
import config

logger = logging.getLogger(__name__)


class FeishuNotifier:
    def __init__(self):
        self.webhook_url = config.FEISHU_CONFIG.get("webhook_url", "")
        self.secret = config.FEISHU_CONFIG.get("secret", "")
        self.enabled = config.FEISHU_CONFIG.get("enabled", False) and bool(self.webhook_url)

    def _sign(self):
        if not self.secret:
            return None
        ts = str(int(time.time()))
        string_to_sign = ts + "\n" + self.secret
        h = hmac.new(self.secret.encode(), string_to_sign.encode(), hashlib.sha256).digest()
        return {"timestamp": ts, "sign": base64.b64encode(h).decode()}

    def send_card(self, title, sections):
        if not self.enabled:
            return False
        try:
            elements = []
            for sec in sections:
                t = sec.get("type")
                if t == "text":
                    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": sec["content"]}})
                elif t == "hr":
                    elements.append({"tag": "hr"})
                elif t == "note":
                    elements.append({"tag": "note", "elements": [{"tag": "plain_text", "content": sec["content"]}]})
            card = {
                "msg_type": "interactive",
                "card": {
                    "header": {"title": {"tag": "plain_text", "content": title}, "template": "blue"},
                    "elements": elements
                }
            }
            sd = self._sign()
            url = self.webhook_url
            if sd:
                url += "&timestamp=" + sd["timestamp"] + "&sign=" + sd["sign"]
            r = requests.post(url, json=card, timeout=10)
            result = r.json()
            code = result.get("code", result.get("StatusCode", -1))
            if code == 0:
                logger.info("Feishu message sent successfully")
                return True
            logger.error("Feishu send failed: %s" % result)
            return False
        except Exception as e:
            logger.error("Feishu send error: %s" % e)
            return False


class WechatNotifier:
    def __init__(self):
        self.enabled = config.WECHAT_CONFIG.get("enabled", False)
        self.push_type = config.WECHAT_CONFIG.get("push_type", "pushplus")
        self.pushplus_token = config.WECHAT_CONFIG.get("pushplus_token", "")
        self.serverchan_key = config.WECHAT_CONFIG.get("serverchan_key", "")

    def send(self, title, content, template=None):
        if not self.enabled:
            logger.info("WeChat not enabled, skip")
            return False
        if self.push_type == "pushplus" and self.pushplus_token:
            return self._send_pushplus(title, content, template)
        elif self.push_type == "serverchan" and self.serverchan_key:
            return self._send_serverchan(title, content)
        logger.warning("Unknown WeChat push type: %s" % self.push_type)
        return False

    def _send_pushplus(self, title, content, template=None):
        try:
            # template 由调用方决定：阶段二默认 markdown 文字报告
            template = template or getattr(config, "PUSHPLUS_TEMPLATE", "html")
            payload = {"token": self.pushplus_token, "title": title,
                       "content": content, "template": template}
            r = requests.post("http://www.pushplus.plus/send", json=payload, timeout=10)
            result = r.json()
            if result.get("code") == 200:
                logger.info("PushPlus sent successfully (template=%s)" % template)
                return True
            logger.error("PushPlus failed: %s" % result)
            return False
        except Exception as e:
            logger.error("PushPlus error: %s" % e)
            return False

    def _send_serverchan(self, title, content):
        try:
            url = "https://sctapi.ftqq.com/%s.send" % self.serverchan_key
            r = requests.post(url, data={"title": title, "desp": content}, timeout=10)
            result = r.json()
            if result.get("code") == 0:
                logger.info("ServerChan sent successfully")
                return True
            logger.error("ServerChan failed: %s" % result)
            return False
        except Exception as e:
            logger.error("ServerChan error: %s" % e)
            return False


feishu_notifier = FeishuNotifier()
wechat_notifier = WechatNotifier()


def format_pushplus_markdown(llm_result, analysis_data=None):
    """生成微信侧 PushPlus markdown 文字报告（决策/评分/风险/催化/免责）。"""
    r = llm_result or {}
    d = r.get("decision", "观望")
    arrow = {"买入": "🟢", "持有": "🔵", "观望": "🟡", "卖出": "🔴"}.get(d, "⚪")
    src = (analysis_data or {}).get("source", "东方财富")
    complete = (analysis_data or {}).get("data_complete", True)
    try:
        conf = float(r.get("confidence", 0)) * 100
    except (TypeError, ValueError):
        conf = 0.0
    lines = []
    lines.append("## 📊 A股 AI 盘前研判")
    lines.append("")
    lines.append("**%s %s** ｜ 研判分 %s/100 ｜ 置信度 %.0f%%" % (arrow, d, r.get("score", "-"), conf))
    if not complete:
        lines.append("> ⚠️ 部分市场数据获取失败，仅供参考")
    lines.append("")
    lines.append("**一句话**：%s" % r.get("summary", ""))
    if r.get("detail"):
        lines.append("")
        lines.append(r.get("detail", ""))
    risks = r.get("risks") or []
    if risks:
        lines.append("")
        lines.append("**⚠️ 风险点**")
        for x in risks[:3]:
            lines.append("- %s" % x)
    cats = r.get("catalysts") or []
    if cats:
        lines.append("")
        lines.append("**🚀 催化/利好**")
        for x in cats[:3]:
            lines.append("- %s" % x)
    if r.get("guardrail_note"):
        lines.append("")
        lines.append("> 🛡️ 护栏提示：%s" % r.get("guardrail_note"))
    lines.append("")
    lines.append("---")
    lines.append("数据来源：%s ｜ AI 仅供参考，不构成投资建议" % src)
    return "\n".join(lines)


def send_market_notification(analysis_data, llm_result=None):
    now = datetime.now()
    date_str = now.strftime("%m月%d日")
    title = "📊 A股 AI 早报 - " + date_str

    indices = analysis_data.get("indices") or []
    breadth = analysis_data.get("breadth") or {}
    north = analysis_data.get("north_flow") or {}
    sectors = analysis_data.get("sectors") or []
    inds = analysis_data.get("indicators") or []
    news = analysis_data.get("news") or []
    up = breadth.get("up", 0)
    dn = breadth.get("down", 0)
    total = breadth.get("total", 0)

    # ===== Build shared content lines (飞书 + 微信 HTML 回退共用) =====
    content_lines = []
    if not analysis_data.get("data_complete", True):
        content_lines.append("⚠️ 部分市场数据获取失败，以下内容仅供参考")
    content_lines.append("**📈 主要指数**")
    if indices:
        for idx in indices[:4]:
            chg = idx.get("chg_pct", 0)
            arrow = "🟢" if chg >= 0 else "🔴"
            content_lines.append("%s **%s**: %.2f  %+.2f%%" % (arrow, idx.get("name", ""), idx.get("price", 0), chg))

    content_lines.append("")
    content_lines.append("**📊 市场涨跌**")
    if total:
        ratio = up / total * 100 if total else 0
        up_lim = breadth.get("up_limit", 0)
        dn_lim = breadth.get("down_limit", 0)
        content_lines.append("上涨: %d家  |  下跌: %d家  |  平盘: %d家" % (up, dn, breadth.get("flat", 0)))
        content_lines.append("涨幅比: %.1f%%  |  涨停: %d  |  跌停: %d" % (ratio, up_lim, dn_lim))

    if north:
        net = north.get("net_inflow", 0)
        arrow = "🟢" if net >= 0 else "🔴"
        content_lines.append("")
        content_lines.append("**💰 北向资金**: %s 净流入 %+.2f亿" % (arrow, net))

    content_lines.append("")
    content_lines.append("**📊 行业板块TOP5**")
    if sectors:
        for s in sectors[:5]:
            chg = s.get("chg", 0)
            lds = ", ".join(["%s(%+.2f%%)" % (l.get("name", ""), l.get("chg", 0)) for l in s.get("leaders", [])[:3]])
            content_lines.append("**%s**: %+.2f%%  -> %s" % (s.get("sector", ""), chg, lds))

    content_lines.append("")
    content_lines.append("**📈 指标图谱 (MACD/KDJ/RSI)**")
    if inds:
        for ind in inds[:4]:
            macd = ind.get("macd", {})
            kdj = ind.get("kdj", {})
            rsi = ind.get("rsi", {})
            content_lines.append("**%s** | MACD:%s | KDJ:%s | RSI:%s" % (
                ind.get("name", ""), macd.get("signal", "-"), kdj.get("signal", "-"), rsi.get("signal", "-")))

    content_lines.append("")
    content_lines.append("**📰 市场要闻**")
    if news:
        for n in news[:5]:
            impact = n.get("impact", "")
            tn = n.get("title", "")[:60]
            content_lines.append("• [%s] %s" % (impact, tn))

    # ===== LLM 研判摘要（追加到飞书卡片） =====
    if llm_result:
        d = llm_result.get("decision", "观望")
        content_lines.append("")
        content_lines.append("**🤖 AI 研判：%s（分%s/100，置信%.0f%%）**" % (
            d, llm_result.get("score", "-"), float(llm_result.get("confidence", 0)) * 100))
        if llm_result.get("summary"):
            content_lines.append("> %s" % llm_result.get("summary"))

    content_lines.append("")
    content_lines.append("---")
    content_lines.append("📧 完整HTML报告已发送至邮箱 | 🤖 化资金讯机器人 | " + now.strftime("%H:%M"))

    # ===== Build Feishu card =====
    feishu_sections = []
    for line in content_lines:
        if line == "":
            continue
        if line.startswith("---"):
            feishu_sections.append({"type": "hr"})
        else:
            feishu_sections.append({"type": "text", "content": line})
    feishu_sections.append({"type": "hr"})
    feishu_sections.append({"type": "note", "content": "🤖 化资金讯机器人 | " + now.strftime("%Y-%m-%d %H:%M")})

    # ===== Dispatch =====
    # 微信侧：有 LLM 结论时用 markdown 文字报告（清晰可读）
    if llm_result:
        wc = format_pushplus_markdown(llm_result, analysis_data)
        w_ok = wechat_notifier.send(title, wc, "markdown")
    else:
        # 回退：原 HTML 报告
        if not analysis_data.get("data_complete", True):
            wc = "<p>⚠️ 部分市场数据获取失败，AI 研判暂不可用，以下内容仅供参考。</p>"
        else:
            wc = ""
        wc += "<h3>📊 A股市场早报 - " + date_str + "</h3>"
        wc += "<h4>📈 主要指数</h4><table>"
        if indices:
            for idx in indices[:4]:
                chg = idx.get("chg_pct", 0)
                color = "#d32f2f" if chg >= 0 else "#388e3c"
                wc += "<tr><td>%s</td><td>%.2f</td><td style=color:%s>%+.2f%%</td></tr>" % (idx.get("name", ""), idx.get("price", 0), color, chg)
        wc += "</table>"

        if total:
            ratio = up / total * 100 if total else 0
            wc += "<p>📊 涨跌: 上涨%d | 下跌%d | 涨幅比%.1f%% | 涨停%d | 跌停%d</p>" % (up, dn, ratio, breadth.get("up_limit", 0), breadth.get("down_limit", 0))

        if north:
            net = north.get("net_inflow", 0)
            wc += "<p>💰 北向资金: 净流入 %+.2f亿</p>" % net

        if sectors:
            wc += "<h4>📊 行业板块TOP5</h4><ul>"
            for s in sectors[:5]:
                chg = s.get("chg", 0)
                lds = ", ".join(["%s(%+.2f%%)" % (l.get("name", ""), l.get("chg", 0)) for l in s.get("leaders", [])[:3]])
                wc += "<li>%s: %+.2f%% (%s)</li>" % (s.get("sector", ""), chg, lds)
            wc += "</ul>"

        if inds:
            wc += "<h4>📈 指标图谱</h4><table><tr><th>指数</th><th>MACD</th><th>KDJ</th><th>RSI</th></tr>"
            for ind in inds[:4]:
                macd = ind.get("macd", {})
                kdj = ind.get("kdj", {})
                rsi = ind.get("rsi", {})
                ms = macd.get("signal", "-")
                ks = kdj.get("signal", "-")
                rs = rsi.get("signal", "-")
                wc += "<tr><td>%s</td><td>%s(DIF:%.2f)</td><td>%s(K:%.1f)</td><td>%s(RSI6:%.1f)</td></tr>" % (ind.get("name", ""), ms, macd.get("dif", 0), ks, kdj.get("k", 0), rs, rsi.get("rsi6", 0))
            wc += "</table>"

        if news:
            wc += "<h4>📰 要闻</h4><ul>"
            for n in news[:5]:
                wc += "<li>[%s] %s</li>" % (n.get("impact", ""), n.get("title", "")[:60])
            wc += "</ul>"

        wc += "<hr><p>📧 <b>完整HTML报告已发送至邮箱</b></p>"
        wc += "<p><small>🤖 化资金讯机器人 | " + now.strftime("%Y-%m-%d %H:%M") + "</small></p>"
        w_ok = wechat_notifier.send(title, wc)

    f_ok = feishu_notifier.send_card(title, feishu_sections)

    logger.info("Notification results - Feishu: %s, WeChat: %s" % (f_ok, w_ok))
    return {"feishu": f_ok, "wechat": w_ok}
