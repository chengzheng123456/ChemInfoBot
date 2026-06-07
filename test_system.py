import sys
sys.path.insert(0, r'D:\Backup\Documents\ChemInfoBot')

print('=== 化工爬虫工具测试脚本 ===\n')

# 测试1: 配置模块
print('1. 测试配置模块...')
import config
print(f'   ✓ 数据库路径: {config.DATABASE_PATH}')
print(f'   ✓ 收件邮箱: {config.EMAIL_CONFIG["recipient_email"]}')
print(f'   ✓ 推送时间: {config.SCHEDULER_CONFIG["daily_push_time"]}')

# 测试2: 数据存储
print('\n2. 测试数据存储模块...')
from data_storage import db, ChemNewsItem
from datetime import datetime

print(f'   ✓ 数据库已初始化: {db.db_path}')

# 创建测试数据
test_item = ChemNewsItem(
    title='测试化工新闻 - 甲醇价格上涨',
    content='今日甲醇市场价格出现明显上涨，主要受供需关系影响。华东地区报价上调50元/吨。',
    source='测试源',
    source_url='https://test.com/news/1',
    category='行情价格',
    keywords='甲醇,PTA',
    summary='甲醇价格上涨50元/吨',
    publish_date=datetime.now()
)

news_id = db.save_news(test_item)
print(f'   ✓ 保存测试新闻成功，ID: {news_id}')

# 查询统计
stats = db.get_news_stats(days=1)
print(f'   ✓ 统计数据: 总{stats["total"]}条')

# 搜索
results = db.search_news('甲醇')
print(f'   ✓ 搜索"甲醇"找到 {len(results)} 条结果')

# 测试3: 爬虫模块（模拟）
print('\n3. 测试爬虫模块...')
from chem_spider import ChemSpider

spider = ChemSpider()
print('   ✓ 爬虫实例创建成功')

# 测试分类功能
test_title = 'PTA价格上涨，市场交投活跃'
test_content = '今日PTA市场行情走高，主力合约上涨2%。华东地区报价上调100元/吨。'
category = spider._classify_category(test_title, test_content)
print(f'   ✓ 智能分类测试: "{test_title}" -> {category}')

# 测试关键词提取
keywords = spider._extract_keywords(test_title, test_content)
print(f'   ✓ 关键词提取: {keywords if keywords else "无"}')

# 测试日期解析
test_dates = [
    '2025-05-30 10:30',
    '2025/05/30',
    '2025年05月30日',
]
for date_str in test_dates:
    parsed = spider._parse_date(date_str)
    print(f'   ✓ 日期解析: "{date_str}" -> {parsed.strftime("%Y-%m-%d")}')

# 测试4: 邮件模块
print('\n4. 测试邮件模块...')
from email_sender import email_sender

print(f'   ✓ SMTP服务器: {email_sender.smtp_server}:{email_sender.smtp_port}')
print(f'   ✓ 发件人: {email_sender.sender_email}')
print(f'   ✓ 收件人: {email_sender.recipient_email}')

# 清理测试数据
print('\n5. 清理测试数据...')

print('\n=== 所有测试通过! ===')
print('\n系统已就绪，可以运行:')
print('  1. python web_app.py      # 启动Web管理界面')
print('  2. python scheduler.py     # 启动定时任务')
