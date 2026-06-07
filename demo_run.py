#!/usr/bin/env python
"""
化工爬虫工具演示 - 模拟完整工作流程
展示爬虫抓取、数据存储、邮件生成的完整流程
"""
import sys
sys.path.insert(0, r'D:\Backup\Documents\ChemInfoBot')

from datetime import datetime, timedelta
from data_storage import db, ChemNewsItem
from email_sender import email_sender

print('=' * 70)
print('  化工行业信息爬虫工具 - 完整演示')
print('  展示: 数据模拟 -> 存储 -> 邮件生成 全流程')
print('=' * 70)

# 模拟抓取的数据
print('\n[1/4] 模拟爬虫抓取化工行业数据...\n')

mock_news = [
    {
        'title': '甲醇：华东市场价格上涨 下游需求增加',
        'content': '今日华东甲醇市场价格上涨50元/吨，主流报价在2450-2500元/吨。' 
                   '下游甲醛、醋酸等行业开工率提升，采购积极性增加。' 
                   '预计短期价格将维持坚挺。',
        'source': '中国化工网',
        'category': '行情价格',
        'keywords': '甲醇',
    },
    {
        'title': 'PTA：大型装置检修 市场供应偏紧',
        'content': '华东某大型PTA装置计划本周检修，预计影响产能120万吨/年。' 
                   '市场供应将趋紧，聚酯工厂按需采购为主。',
        'source': '隆众资讯',
        'category': '行情价格',
        'keywords': 'PTA,聚酯',
    },
    {
        'title': '聚乙烯：新产能投产 市场价格承压',
        'content': '某石化企业80万吨/年PE装置近日投产，市场供应量增加。' 
                   '下游需求恢复缓慢，现货价格小幅下跌。',
        'source': '中国化工网',
        'category': '行业动态',
        'keywords': 'PE,聚乙烯',
    },
    {
        'title': '苯乙烯：库存下降 市场心态好转',
        'content': '本周苯乙烯港口库存环比下降5%，市场供应压力缓解。' 
                   '下游EPS、PS行业开工稳定，需求支撑尚可。',
        'source': '隆众资讯',
        'category': '市场分析',
        'keywords': '苯乙烯,EPS,PS',
    },
    {
        'title': '丙烯：下游采购积极 价格小幅上调',
        'content': '今日丙烯市场价格上涨30-50元/吨，聚丙烯、环氧丙烷等' 
                   '下游产品需求良好，采购积极性较高。',
        'source': '中国铁合金在线',
        'category': '行情价格',
        'keywords': '丙烯,PP',
    },
]

print(f'模拟抓取到 {len(mock_news)} 条化工行业资讯:')
for i, news in enumerate(mock_news, 1):
    print(f'  [{i}] {news["title"]} ({news["source"]}) - {news["category"]}')

# 保存到数据库
print('\n[2/4] 保存数据到SQLite数据库...\n')

saved_ids = []
for news in mock_news:
    item = ChemNewsItem(
        title=news['title'],
        content=news['content'],
        source=news['source'],
        source_url=f'https://example.com/news/{datetime.now().timestamp()}',
        category=news['category'],
        keywords=news['keywords'],
        summary=news['content'][:100] + '...',
        publish_date=datetime.now(),
        is_sent=False
    )
    nid = db.save_news(item)
    saved_ids.append(nid)
    print(f'  ✓ 已保存: {news["title"][:40]}... (ID: {nid})')

print(f'\n共保存 {len(saved_ids)} 条数据')

# 统计
print('\n[3/4] 生成统计信息...\n')
stats = db.get_news_stats(days=1)
print('今日数据统计:')
print(f'  • 总条数: {stats["total"]} 条')
print(f'  • 行情价格: {stats.get("by_category", {}).get("行情价格", 0)} 条')
print(f'  • 行业动态: {stats.get("by_category", {}).get("行业动态", 0)} 条')
print(f'  • 市场分析: {stats.get("by_category", {}).get("市场分析", 0)} 条')
print(f'  • 数据来源: {", ".join(stats.get("by_source", {}).keys())}')

# 获取未发送的新闻
print('\n[4/4] 生成邮件内容...\n')
unsent = db.get_unsent_news(limit=50)
print(f'找到 {len(unsent)} 条未推送新闻')

# 生成邮件内容
if unsent:
    print('\n' + '-' * 70)
    print('邮件预览 (HTML格式):')
    print('-' * 70)
    
    # 按分类整理
    categorized = {}
    for item in unsent:
        cat = item.category if item.category in ['行情价格', '行业动态', '市场分析', '政策法规'] else '其他'
        categorized.setdefault(cat, []).append(item)
    
    print(f'\n主题: 【化工早讯】{datetime.now().strftime("%m月%d日")}行业动态({len(unsent)}条)\n')
    
    for cat, items in categorized.items():
        print(f'\n【{cat}】({len(items)}条)')
        print('=' * 50)
        for item in items:
            print(f'  • {item.title}')
            print(f'    来源: {item.source} | {item.publish_date.strftime("%m-%d %H:%M")}')
            if item.keywords:
                print(f'    关键词: {item.keywords}')
            print(f'    摘要: {item.summary[:80]}...')
            print()
    
    print('-' * 70)
    print(f'收件人: cz9721@163.com')
    print(f'发送时间: 每天 08:30 (定时任务)')
    print('-' * 70)

print('\n' + '=' * 70)
print('演示完成!')
print('=' * 70)
print('\n实际使用说明:')
print('  1. 修改 config.py 中的邮箱配置 (必须使用163邮箱SMTP授权码)')
print('  2. 运行: python web_app.py 启动Web管理界面')
print('  3. 运行: python scheduler.py 启动定时后台任务')
print('  4. 访问: http://localhost:5000 查看管理界面')
print('\n定时任务配置:')
print('  • 爬虫任务: 每2小时自动抓取')
print('  • 邮件推送: 每天早上 08:30 自动发送')
print('  • 数据清理: 每周日凌晨 2:00 清理30天前数据')
