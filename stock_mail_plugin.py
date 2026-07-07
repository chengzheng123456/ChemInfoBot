# Stock market email plugin - Enhanced with comprehensive A-share analysis
import logging
from datetime import datetime, timedelta
import config
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email_sender import email_sender, db
from a_stock_spider import AStockSpider, MarketNewsSpider
from notification_sender import feishu_notifier, wechat_notifier, send_market_notification
from market_report import generate_market_report, generate_compact_report, REPORT_CSS
logger = logging.getLogger(__name__)

def send_enhanced():
    logger.info("Starting enhanced email with comprehensive A-share analysis")
    try:
        spider = AStockSpider()
        s = spider.fetch_sector_rankings(3)
        m = MarketNewsSpider().fetch_news()
        try:
            analysis = spider.fetch_previous_trading_day_analysis()
        except Exception as e:
            logger.warning("Market analysis fetch failed: %s" % e)
            analysis = None
    except:
        s, m, analysis = [], [], None

    items = db.get_latest_news(hours=24, limit=50)
    if not items and not s and not analysis:
        logger.info("No data")
        return False

    now = datetime.now()
    sub = "化工资讯日报 - " + now.strftime("%m月%d日")

    html_parts = []
    html_parts.append("<html><head><meta charset=utf-8><style>" + REPORT_CSS + "</style></head><body>")

    # Comprehensive market report
    if analysis:
        report_html = generate_market_report(analysis)
        html_parts.append(report_html)
    else:
        html_parts.append("<div class=header><h1>化工资讯早报</h1><p>" + now.strftime("%Y年%m月%d日") + "</p></div>")

    # Sector rankings
    if s:
        html_parts.append("<div class=card><div class=card-title>A股行业涨幅前三</div><table><tr><th>排名</th><th>板块</th><th>涨幅</th><th>领涨股</th></tr>")
        for x in s:
            clr = "#d32f2f" if x.get("chg",0) >= 0 else "#388e3c"
            ld = ", ".join([l.get("name","") for l in x.get("leaders",[])])
            html_parts.append("<tr><td>" + str(x.get("rank","")) + "</td><td style=font-weight:bold>" + x.get("sector","") + "</td><td style=color:" + clr + ";font-weight:bold>" + ("%.2f%%" % x.get("chg",0)) + "</td><td>" + ld + "</td></tr>")
        html_parts.append("</table></div>")

    # Market news
    if m:
        html_parts.append("<div class=card><div class=card-title>市场要闻</div>")
        for n in m[:8]:
            html_parts.append("<div style=padding:5px 0;border-bottom:1px solid #eee><a href=" + n.get("url","#") + " style=color:#1a237e;text-decoration:none>" + n.get("title","") + "</a><br/><small>" + n.get("source","") + " | " + n.get("impact","") + "</small></div>")
        html_parts.append("</div>")

    # Chemical news from DB
    if items:
        html_parts.append("<div class=card><div class=card-title>化工资讯</div>")
        for it in items[:15]:
            d = it.publish_date.strftime("%m-%d") if it.publish_date else ""
            html_parts.append("<div style=padding:5px 0;border-bottom:1px solid #eee><a href=" + str(it.source_url) + " style=color:#1a237e;text-decoration:none>" + str(it.title) + "</a><br/><small>" + str(it.source) + " | " + d + "</small></div>")
        html_parts.append("</div>")

    html_parts.append("<div class=footer><p>化工资讯机器人自动发送</p></div>")
    html_parts.append("</body></html>")
    html = "\n".join(html_parts)

    # Save report HTML to disk for reference
    try:
        import os
        report_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, "market_report_{}.html".format(now.strftime("%Y%m%d")))
        with open(report_path, "w", encoding="utf-8") as rf:
            rf.write(html)
        report_path_latest = os.path.join(report_dir, "market_report_latest.html")
        with open(report_path_latest, "w", encoding="utf-8") as rf:
            rf.write(html)
        logger.info("Report saved to: %s" % report_path)
    except Exception as e:
        logger.warning("Report save failed: %s" % e)
        report_path = ""

    # Send email
    email_ok = False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = Header("化工资讯机器人 <" + email_sender.sender_email + ">", "utf-8")
        msg["To"] = Header(email_sender.recipient_email, "utf-8")
        msg["Subject"] = Header(sub, "utf-8")
        msg.attach(MIMEText(html, "html", "utf-8"))
        with email_sender._create_smtp_connection() as srv:
            srv.sendmail(email_sender.sender_email, [email_sender.recipient_email], msg.as_string())
        db.log_email_send(email_sender.recipient_email, sub, 1, "success")
        logger.info("Enhanced email sent: " + sub)
        if items:
            db.mark_as_sent([n.id for n in items if n.id])
        email_ok = True
    except Exception as e:
        db.log_email_send(email_sender.recipient_email, sub, 0, "failed", str(e))
        logger.error("Enhanced email failed: " + str(e))
        try:
            email_ok = email_sender.send_daily_digest()
        except:
            pass

    # Persist A股 snapshot for traceability (phase-1)
    if analysis:
        try:
            snap_id = db.save_market_snapshot(analysis)
            logger.info("Market snapshot saved, id=%s", snap_id)
        except Exception as e:
            logger.warning("Snapshot save failed: %s" % e)

    # Push to Feishu and WeChat
    if analysis:
        try:
            result = send_market_notification(analysis)
            logger.info("Multi-channel push: %s" % result)
        except Exception as e:
            logger.error("Push failed: %s" % e)

    return email_ok


if __name__ == "__main__":
    send_enhanced()
