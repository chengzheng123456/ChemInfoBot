"""
化工行业信息爬虫工具 - 邮件发送模块
支持HTML格式邮件，定时推送最新化工行业信息
"""

import smtplib
import logging
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import List, Dict, Any

import config
from data_storage import db, ChemNewsItem

# 配置日志
logging.basicConfig(
    level=config.LOG_CONFIG["level"],
    format=config.LOG_CONFIG["format"],
)
logger = logging.getLogger(__name__)


class EmailSender:
    """邮件发送器"""
    
    def __init__(self):
        self.smtp_server = config.EMAIL_CONFIG['smtp_server']
        self.smtp_port = config.EMAIL_CONFIG['smtp_port']
        self.sender_email = config.EMAIL_CONFIG['sender_email']
        self.sender_password = config.EMAIL_CONFIG['sender_password']
        self.recipient_email = config.EMAIL_CONFIG['recipient_email']
        self.use_ssl = config.EMAIL_CONFIG['use_ssl']
    
    def _create_smtp_connection(self):
        """创建SMTP连接"""
        if self.use_ssl:
            server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
        else:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
        
        server.login(self.sender_email, self.sender_password)
        return server
    
    def send_news_digest(
        self, 
        news_items: List[ChemNewsItem],
        subject: str = None
    ) -> bool:
        """
        发送新闻摘要邮件
        参数:
            news_items: 新闻列表
            subject: 邮件主题(可选)
        返回: 是否发送成功
        """
        if not news_items:
            logger.warning("没有新闻可发送")
            return False
        
        try:
            # 构建邮件内容
            html_content = self._build_email_content(news_items)
            
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['From'] = Header(f'化工资讯机器人 <{self.sender_email}>', 'utf-8')
            msg['To'] = Header(self.recipient_email, 'utf-8')
            
            # 设置主题
            if not subject:
                today = datetime.now().strftime('%m月%d日')
                subject = f'【化工早讯】{today}行业动态({len(news_items)}条)'
            
            msg['Subject'] = Header(subject, 'utf-8')
            
            # 添加HTML内容
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # 发送邮件
            with self._create_smtp_connection() as server:
                server.sendmail(
                    self.sender_email,
                    [self.recipient_email],
                    msg.as_string()
                )
            
            # 记录发送成功
            db.log_email_send(
                recipient=self.recipient_email,
                subject=subject,
                items_count=len(news_items),
                status="success"
            )
            
            logger.info(f"邮件发送成功: {subject} ({len(news_items)} 条新闻)")
            return True
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"邮件发送失败: {error_msg}")
            
            # 记录发送失败
            db.log_email_send(
                recipient=self.recipient_email,
                subject=subject or "邮件发送",
                items_count=len(news_items),
                status="failed",
                error_message=error_msg
            )
            return False
    
    def _build_email_content(self, news_items: List[ChemNewsItem]) -> str:
        """构建HTML邮件内容"""
        today = datetime.now().strftime('%Y年%m月%d日 %A')
        
        # 按分类分组
        categorized = self._categorize_news(news_items)
        
        # 统计信息
        stats = self._generate_stats(news_items)
        
        # 构建HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>化工早讯</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f5f5;
                }}
                .header {{
                    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 10px 10px 0 0;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 24px;
                }}
                .header .date {{
                    margin-top: 10px;
                    opacity: 0.9;
                }}
                .stats {{
                    background: #fff;
                    padding: 20px;
                    border-bottom: 2px solid #e0e0e0;
                }}
                .stats-grid {{
                    display: grid;
                    grid-template-columns: repeat(4, 1fr);
                    gap: 15px;
                    text-align: center;
                }}
                .stat-item {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 8px;
                }}
                .stat-number {{
                    font-size: 28px;
                    font-weight: bold;
                    color: #2a5298;
                }}
                .stat-label {{
                    font-size: 12px;
                    color: #666;
                    margin-top: 5px;
                }}
                .category-section {{
                    margin: 20px 0;
                }}
                .category-title {{
                    background: #e8f4f8;
                    padding: 12px 20px;
                    border-left: 4px solid #2a5298;
                    font-size: 16px;
                    font-weight: bold;
                    color: #2a5298;
                    margin: 0;
                }}
                .news-list {{
                    background: #fff;
                    padding: 0;
                    margin: 0;
                    list-style: none;
                }}
                .news-item {{
                    padding: 15px 20px;
                    border-bottom: 1px solid #eee;
                }}
                .news-item:last-child {{
                    border-bottom: none;
                }}
                .news-title {{
                    font-size: 15px;
                    font-weight: 600;
                    color: #333;
                    margin-bottom: 8px;
                }}
                .news-title a {{
                    color: #333;
                    text-decoration: none;
                }}
                .news-title a:hover {{
                    color: #2a5298;
                }}
                .news-meta {{
                    font-size: 12px;
                    color: #999;
                    margin-bottom: 8px;
                }}
                .news-summary {{
                    font-size: 13px;
                    color: #666;
                    line-height: 1.6;
                }}
                .keywords {{
                    margin-top: 8px;
                }}
                .keyword {{
                    display: inline-block;
                    background: #e8f4f8;
                    color: #2a5298;
                    padding: 2px 8px;
                    border-radius: 3px;
                    font-size: 11px;
                    margin-right: 5px;
                }}
                .footer {{
                    background: #333;
                    color: #999;
                    text-align: center;
                    padding: 20px;
                    font-size: 12px;
                    border-radius: 0 0 10px 10px;
                }}
                .footer a {{
                    color: #999;
                }}
                @media (max-width: 600px) {{
                    .stats-grid {{
                        grid-template-columns: repeat(2, 1fr);
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🧪 化工行业每日资讯</h1>
                <div class="date">{today}</div>
            </div>
            
            <div class="stats">
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-number">{stats['total']}</div>
                        <div class="stat-label">总条数</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{stats['行情价格']}</div>
                        <div class="stat-label">行情价格</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{stats['行业动态']}</div>
                        <div class="stat-label">行业动态</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{stats['市场分析']}</div>
                        <div class="stat-label">市场分析</div>
                    </div>
                </div>
            </div>
        """
        
        # 添加各分类的新闻
        for category, items in categorized.items():
            if not items:
                continue
            
            html += f"""
            <div class="category-section">
                <div class="category-title">{category} ({len(items)}条)</div>
                <ul class="news-list">
            """
            
            for item in items[:5]:  # 每类最多显示5条
                keywords_html = ""
                if item.keywords:
                    keywords = item.keywords.split(',')[:3]  # 最多显示3个关键词
                    keywords_html = ''.join([f'<span class="keyword">{k}</span>' for k in keywords])
                
                date_str = item.publish_date.strftime('%m-%d %H:%M') if item.publish_date else ""
                
                html += f"""
                <li class="news-item">
                    <div class="news-title">
                        <a href="{item.source_url}" target="_blank">{item.title}</a>
                    </div>
                    <div class="news-meta">
                        {item.source} | {date_str}
                    </div>
                    <div class="news-summary">{item.summary or item.content[:150]}...</div>
                    <div class="keywords">{keywords_html}</div>
                </li>
                """
            
            html += """
                </ul>
            </div>
            """
        
        html += f"""
            <div class="footer">
                <p>此邮件由 化工资讯爬虫机器人 自动发送</p>
                <p>发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>如需管理，请访问本地管理界面</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _categorize_news(self, news_items: List[ChemNewsItem]) -> Dict[str, List[ChemNewsItem]]:
        """按分类整理新闻"""
        categories = {
            '行情价格': [],
            '行业动态': [],
            '市场分析': [],
            '政策法规': [],
            '其他': []
        }
        
        for item in news_items:
            cat = item.category if item.category in categories else '其他'
            categories[cat].append(item)
        
        return categories
    
    def _generate_stats(self, news_items: List[ChemNewsItem]) -> Dict[str, int]:
        """生成统计信息"""
        stats = {
            'total': len(news_items),
            '行情价格': 0,
            '行业动态': 0,
            '市场分析': 0,
            '政策法规': 0,
            '其他': 0
        }
        
        for item in news_items:
            if item.category in stats:
                stats[item.category] += 1
            else:
                stats['其他'] += 1
        
        return stats
    
    def send_daily_digest(self, hours: int = 24) -> bool:
        """
        发送每日摘要
        参数:
            hours: 获取最近N小时的新闻
        返回: 是否发送成功
        """
        logger.info(f"准备发送每日摘要 (最近{hours}小时)")
        
        # 获取未发送的新闻
        news_items = db.get_latest_news(hours=hours, limit=50)
        
        if not news_items:
            logger.info("没有新数据需要发送")
            return False
        
        # 发送邮件
        result = self.send_news_digest(news_items)
        
        if result:
            # 标记为已发送
            news_ids = [item.id for item in news_items if item.id]
            db.mark_as_sent(news_ids)
            logger.info(f"已标记 {len(news_ids)} 条新闻为已发送")
        
        return result
    
    def test_connection(self) -> bool:
        """测试邮件连接"""
        try:
            with self._create_smtp_connection():
                logger.info("SMTP连接测试成功")
                return True
        except Exception as e:
            logger.error(f"SMTP连接测试失败: {e}")
            return False


# 全局邮件发送器实例
email_sender = EmailSender()


def send_daily_email():
    """每日邮件任务入口"""
    logger.info("=" * 50)
    logger.info("开始执行每日邮件推送任务")
    logger.info("=" * 50)
    
    result = email_sender.send_daily_digest()
    
    if result:
        logger.info("每日邮件推送成功！")
    else:
        logger.warning("每日邮件推送失败或无需推送")
    
    return result


def test_email():
    """测试邮件功能"""
    print("测试邮件发送...")
    
    # 先测试连接
    if not email_sender.test_connection():
        print("SMTP连接测试失败，请检查邮箱配置")
        return False
    
    # 发送测试邮件
    result = email_sender.send_news_digest(
        news_items=[ChemNewsItem(
            title="测试邮件",
            content="这是一封测试邮件，用于验证邮件功能是否正常。",
            source="测试系统",
            source_url="https://example.com",
            category="测试",
            publish_date=datetime.now(),
        )],
        subject="【测试】化工资讯机器人邮件测试"
    )
    
    return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_email()
    else:
        # 实际发送每日邮件
        send_daily_email()
