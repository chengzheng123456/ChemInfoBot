# Comprehensive A-share market report generator
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

REPORT_CSS = """body{font-family:system-ui,Microsoft YaHei,sans-serif;background:#f0f2f5;margin:0;padding:0;color:#333}.container{max-width:750px;margin:0 auto;padding:15px}.card{background:#fff;border-radius:12px;padding:18px;margin-bottom:15px;box-shadow:0 2px 8px rgba(0,0,0,0.06)}.card-title{font-size:17px;font-weight:700;color:#1a237e;margin:0 0 12px 0;padding-bottom:8px;border-bottom:2px solid #534bae}.header{background:linear-gradient(135deg,#1a237e,#534bae);color:#fff;padding:28px 20px;border-radius:12px;text-align:center;margin-bottom:15px}.up{color:#d32f2f;font-weight:600}.down{color:#388e3c;font-weight:600}table{width:100%;border-collapse:collapse;font-size:13px}th{background:#f5f5f5;padding:8px 6px;text-align:left;font-weight:600;border-bottom:2px solid #ddd}td{padding:7px 6px;border-bottom:1px solid #eee}.footer{text-align:center;color:#999;font-size:12px;padding:15px 0}"""
def generate_market_report(analysis_data):
    if not analysis_data:
        return "<p>No data</p>"
    now = datetime.now()
    d = now.strftime("%Y年%m月%d日")
    s = []
    s.append("<div class=container>")
    s.append("<div class=header><h1>A股市场早报</h1><p>" + d + "</p></div>")
    idx = analysis_data.get("indices", [])
    brd = analysis_data.get("breadth", {})
    nf = analysis_data.get("north_flow", {})
    tot = brd.get("total", 0)
    up = brd.get("up", 0)
    dn = brd.get("down", 0)
    sum_html = "<div class=card><div class=card-title>市场概览</div>"
    if idx:
        sh = idx[0] if idx else {}
        sc = sh.get("chg_pct", 0)
        tr = "上涨" if sc >= 0 else "下跌"
        pfx = "<span class=up>+" if sc >= 0 else "<span class=down>"
        sum_html += "<p>A股三大指数集体" + tr + "，上证指数收报" + str(round(sh.get("price",0),2)) + "点，涨跌幅" + pfx + "{:.2f}%</span></p>".format(sc)
    if tot:
        r = up/tot*100 if tot else 0
        sum_html += "<p>全市场{}只个股中，<span class=up>{}只上涨</span>，<span class=down>{}只下跌</span>，涨跌比 {:.1f}%</p>".format(tot, up, dn, r)
    if nf:
        net = nf.get("net_inflow", 0)
        dr = "净流入" if net >= 0 else "净流出"
        sum_html += "<p>北向资金: " + dr + " {:+.2f}亿</p>".format(net)
    sum_html += "</div>"
    s.append(sum_html)
    # Index table
    if idx:
        tbl = "<div class=card><div class=card-title>主要指数行情</div><table><tr><th>指数</th><th>最新价</th><th>涨跌幅</th><th>涨跌额</th><th>今开</th><th>最高</th><th>最低</th></tr>"
        for x in idx:
            cg = x.get("chg_pct", 0)
            cl = "up" if cg >= 0 else "down"
            tbl += "<tr><td><b>{}</b></td><td>{:.2f}</td><td class={}>{:+.2f}%</td><td>{:+.2f}</td><td>{:.2f}</td><td>{:.2f}</td><td>{:.2f}</td></tr>".format(x.get("name",""), x.get("price",0), cl, cg, x.get("chg_val",0), x.get("open",0), x.get("high",0), x.get("low",0))
        tbl += "</table></div>"
        s.append(tbl)

    # Market breadth
    if brd:
        bd = "<div class=card><div class=card-title>市场涨跌分布</div>"
        up = brd.get("up", 0)
        dn = brd.get("down", 0)
        fl = brd.get("flat", 0)
        ul = brd.get("up_limit", 0)
        dl = brd.get("down_limit", 0)
        tb = up + dn + fl
        if tb > 0:
            uw = up/tb*100
            dw = dn/tb*100
            fw = fl/tb*100
            bd += "<div style=display:flex;height:24px;border-radius:12px;overflow:hidden;margin:10px 0><div style=width:{:.1f}%;background:linear-gradient(90deg,#ef5350,#e57373);display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px;font-weight:600>{}上涨</div><div style=width:{:.1f}%;background:#bbb;display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px>{}平</div><div style=width:{:.1f}%;background:linear-gradient(90deg,#66bb6a,#81c784);display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px;font-weight:600>{}下跌</div></div>".format(uw, up, fw, fl, dw, dn)
            bd += "<div style=display:flex;justify-content:space-between;font-size:12px;color:#666><span>涨停: {}只</span><span>上涨: {:.1f}%</span><span>平盘: {:.1f}%</span><span>下跌: {:.1f}%</span><span>跌停: {}只</span></div>".format(ul, uw, fw, dw, dl)
        bd += "</div>"
        s.append(bd)

    # Top gainers/losers
    gn = brd.get("top_gainers", [])
    ls = brd.get("top_losers", [])
    if gn or ls:
        gl = "<div class=card><div class=card-title>涨跌龙虎榜</div><div style=display:flex;gap:15px>"
        if gn:
            gl += "<div style=flex:1><b style=color:#d32f2f>涨幅榜</b><table>"
            for g in gn[:5]:
                gl += "<tr><td>{}</td><td>{}</td><td class=up>{:+.2f}%</td></tr>".format(g.get("name",""), g.get("code",""), g.get("chg",0))
            gl += "</table></div>"
        if ls:
            gl += "<div style=flex:1><b style=color:#388e3c>跌幅榜</b><table>"
            for l in ls[:5]:
                gl += "<tr><td>{}</td><td>{}</td><td class=down>{:+.2f}%</td></tr>".format(l.get("name",""), l.get("code",""), l.get("chg",0))
            gl += "</table></div>"
        gl += "</div></div>"
        s.append(gl)
    # Sector analysis
    secs = analysis_data.get("sectors", [])
    if secs:
        sh = "<div class=card><div class=card-title>行业板块涨幅TOP5</div><table><tr><th>排名</th><th>板块</th><th>涨幅</th><th>领涨个股</th></tr>"
        for i, si in enumerate(secs[:5]):
            cg = si.get("chg", 0)
            cl = "up" if cg >= 0 else "down"
            leaders = si.get("leaders", [])[:3]
            ld_parts = []
            for l in leaders:
                lc = l.get("chg", 0)
                lclr = "#d32f2f" if lc >= 0 else "#388e3c"
                ld_parts.append("<span style=color:{};font-weight:600>{}<span>({:+.2f}%)</span></span>".format(lclr, l.get("name",""), lc))
            ld = "<br>".join(ld_parts)
            sh += "<tr><td>{}</td><td><b>{}</b></td><td class={}>{:+.2f}%</td><td style=font-size:12px>{}</td></tr>".format(i+1, si.get("sector",""), cl, cg, ld)
        sh += "</table></div>"
        s.append(sh)

    # Market sentiment and strategy
    up_ratio = up/tb*100 if tb and up else 50
    sent = "偏多" if up_ratio >= 60 else ("偏空" if up_ratio <= 40 else "中性")
    sc = "#d32f2f" if up_ratio >= 60 else ("#388e3c" if up_ratio <= 40 else "#ff9800")
    st = "<div class=card><div class=card-title>市场情绪与策略建议</div>"
    st += "<div style=display:flex;align-items:center;gap:15px;margin:10px 0><div style=font-size:36px;font-weight:700;color:{}>{}<div><div style=flex:1><div style=height:8px;border-radius:4px;width:{:.1f}%;background:{}></div><div style=font-size:12px;color:#999;margin-top:5px>市场情绪指数: {:.1f} (基于涨跌比计算)<div><div></div>".format(sc, sent, up_ratio, sc, up_ratio)
    if up_ratio >= 60:
        strs = ["市场情绪偏乐观，可适当增加仓位", "关注领涨板块的持续性，把握龙头机会", "注意高位追涨风险，设置合理止盈位"]
    elif up_ratio <= 40:
        strs = ["市场情绪偏谨慎，建议控制仓位", "关注防御性板块，如公用事业、消费", "逢低布局优质标的，等待市场企稳信号"]
    else:
        strs = ["市场处于震荡格局，建议均衡配置", "关注结构性机会，精选个股为主", "控制仓位在5-7成，灵活应对"]
    st += "<div style=margin-top:15px><b>操作策略建议:<b><ul>"
    for sts in strs:
        st += "<li>" + sts + "<li>"
    st += "</ul></div></div>"
    s.append(st)

    # 
    # Technical indicators
    inds = analysis_data.get("indicators", [])
    if inds:
        itbl = "<div class=card><div class=card-title>指标图谱 (MACD/KDJ/RSI)</div><table><tr><th>指数</th><th>MACD(DIF/DEA)</th><th>信号</th><th>KDJ(K/D/J)</th><th>信号</th><th>RSI(6/12/24)</th><th>信号</th></tr>"
        for ind in inds:
            macd = ind.get("macd", {})
            kdj = ind.get("kdj", {})
            rsi = ind.get("rsi", {})
            itbl += "<tr><td><b>" + ind.get("name","") + "</b></td>"
            itbl += "<td>" + str(macd.get("dif","-")) + "/" + str(macd.get("dea","-")) + "</td>"
            ms = macd.get("signal","-")
            mc = "up" if ms in ["金叉","多头"] else "down"
            itbl += "<td class=" + mc + ">" + ms + "</td>"
            itbl += "<td>" + str(kdj.get("k","-")) + "/" + str(kdj.get("d","-")) + "/" + str(kdj.get("j","-")) + "</td>"
            ks = kdj.get("signal","-")
            kc = "up" if ks in ["低位金叉","超买"] else ("down" if ks in ["高位死叉","超卖"] else "")
            itbl += "<td class=" + kc + ">" + ks + "</td>"
            itbl += "<td>" + str(rsi.get("rsi6","-")) + "/" + str(rsi.get("rsi12","-")) + "/" + str(rsi.get("rsi24","-")) + "</td>"
            rs = rsi.get("signal","-")
            rc = "up" if rs in ["超买"] else ("down" if rs in ["超卖"] else "")
            itbl += "<td class=" + rc + ">" + rs + "</td></tr>"
        itbl += "</table>"
        itbl += "<p style=font-size:11px;color:#999;margin:5px 0>金叉/死叉: MACD与信号线交叉信号 | KDJ超买超卖: J值<0或>100 | RSI>80超卖 RSI<20超买</p>"
        itbl += "</div>"
    s.append(itbl)

    # Footer
    # Footer with honest data provenance (phase-1)
    src = analysis_data.get("source") or "东方财富"
    if analysis_data.get("data_complete", True):
        provenance = "数据来源: " + src
    else:
        provenance = "数据来源: " + src + "（部分数据获取失败，以下内容仅供参考）"
    s.append("<div class=footer><p>化工资讯机器人自动生成 | " + provenance + " | 仅供参考，不构成投资建议</p><p>" + now.strftime("%Y-%m-%d %H:%M:%S") + "</p></div>")
    s.append("</div>")
    return "\n".join(s)


def generate_llm_report(analysis_data, llm_result):
    """在真实数据报告之上叠加 AI 研判卡（决策徽章/评分/置信度/风险/催化/免责）。"""
    if not analysis_data or not llm_result:
        return generate_market_report(analysis_data)
    base = generate_market_report(analysis_data)
    r = llm_result
    decision = r.get("decision", "观望")
    dcolor = {"买入": "#d32f2f", "持有": "#1565c0", "观望": "#ff9800",
              "卖出": "#388e3c"}.get(decision, "#607d8b")
    arrow = {"买入": "🟢", "持有": "🔵", "观望": "🟡", "卖出": "🔴"}.get(decision, "⚪")
    score = r.get("score", "-")
    try:
        conf = float(r.get("confidence", 0))
    except (TypeError, ValueError):
        conf = 0.0
    summary = r.get("summary", "")
    detail = r.get("detail", "")
    risks = r.get("risks") or []
    cats = r.get("catalysts") or []
    guard = r.get("guardrail_note", "")

    card = "<div class=card style='border-left:5px solid %s'>" % dcolor
    card += "<div class=card-title>🤖 AI 盘前研判（DeepSeek）</div>"
    card += "<div style='display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin:6px 0'>"
    card += "<div style='font-size:28px;font-weight:800;color:%s'>%s %s</div>" % (dcolor, arrow, decision)
    card += "<div style='font-size:13px;color:#555'>综合研判分 <b>%s</b>/100 ｜ 置信度 <b>%.0f%%</b></div>" % (score, conf * 100)
    card += "</div>"
    if summary:
        card += "<p style='margin:6px 0;font-size:15px;font-weight:600'>%s</p>" % summary
    if detail:
        card += "<p style='margin:4px 0;color:#444;font-size:13px'>%s</p>" % detail
    if risks:
        card += "<div style='margin-top:8px'><b style='color:#d32f2f'>⚠️ 风险点</b><ul style='margin:4px 0;padding-left:18px;font-size:13px'>"
        for x in risks[:3]:
            card += "<li>%s</li>" % x
        card += "</ul></div>"
    if cats:
        card += "<div style='margin-top:6px'><b style='color:#2e7d32'>🚀 催化/利好</b><ul style='margin:4px 0;padding-left:18px;font-size:13px'>"
        for x in cats[:3]:
            card += "<li>%s</li>" % x
        card += "</ul></div>"
    if guard:
        card += "<p style='margin-top:8px;font-size:12px;color:#ef6c00'>🛡️ 护栏提示：%s</p>" % guard
    card += "<p style='margin-top:8px;font-size:11px;color:#999'>%s</p>" % r.get("disclaimer", "AI 仅供参考，不构成投资建议")
    card += "</div>"

    return base.replace("<div class=header>", card + "\n<div class=header>", 1)


def generate_compact_report(analysis_data):
    if not analysis_data:
        return "No data"
    idx = analysis_data.get("indices", [])
    brd = analysis_data.get("breadth", {})
    lines = []
    if idx:
        for x in idx[:4]:
            cg = x.get("chg_pct", 0)
            lines.append("{}: {:.2f} ({:+.2f}%)".format(x.get("name",""), x.get("price",0), cg))
    if brd:
        lines.append("涨跌: {}/{}".format(brd.get("up",0), brd.get("down",0)))
    return "\n".join(lines)