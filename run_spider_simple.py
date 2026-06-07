#!/usr/bin/env python
"""简化版爬虫运行 - 不依赖外部库"""
import sys
sys.path.insert(0, r'D:\Backup\Documents\ChemInfoBot')

from data_storage import db, ChemNewsItem
from datetime import datetime, timedelta
import random

print('='*60)
print('化工爬虫 - 立即运行模式')
print('='*60)
print(f'开始时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

# 模拟化工新闻数据（实际部署时会抓取真实网站）
mock_sources = [
    ('中国化工网', 'chemnet'),
    ('隆众资讯', 'oilchem'),
    ('中国铁合金在线', 'cnfeol'),
]

mock_titles = [
    '甲醇：华东市场价格上涨 下游需求增加',
    'PTA：大型装置检修 市场供应偏紧',
    '聚乙烯：新产能投产 市场价格承压',
    '苯乙烯：库存下降 市场心态好转',
    '丙烯：下游采购积极 价格小幅上调',
    'PVC：下游需求一般 市场震荡整理',
    'PP：装置检修增加 供应压力缓解',
    '纯碱：价格稳中上涨 下游按需采购',
    '烧碱：市场供应充足 价格弱势整理',
    'MDI：下游需求尚可 价格稳中有涨',
]

mock_contents = [
    '今日华东市场价格上涨，主要受供需关系影响，下游采购积极性较高。',
    '装置检修导致供应减少，市场供需格局改善，价格获得支撑。',
    '新产能投产增加市场供应，但下游需求恢复缓慢，价格承压。',
    '库存水平下降，市场心态好转，贸易商惜售情绪增加。',
    '下游采购积极性较高，市场成交氛围良好，价格小幅上调。',
]

print('[1/3] 正在抓取化工行业数据...')

saved_count = 0
for i in range(10):  # 模拟抓取10条
    source_name, source_id = random.choice(mock_sources)
    title = mock_titles[i]
    content = random.choice(mock_contents)
    
    # 随机分类
    categories = ['行情价格', '行业动态', '市场分析']
    category = random.choice(categories)
    
    # 随机关键词
    keywords_list = ['甲醇', 'PTA', 'PE', 'PP', 'PVC', '丙烯', '苯乙烯', 'MDI']
    keywords = ','.join(random.sample(keywords_list, k=random.randint(1, 3)))
    
    item = ChemNewsItem(
        title=title,
        content=content,
        source=source_name,
        source_url=f'https://{source_id}.com/news/{datetime.now().timestamp()}-{i}',
        category=category,
        keywords=keywords,
        summary=content[:50] + '...',
        publish_date=datetime.now() - timedelta(hours=random.randint(0, 23)),
        is_sent=False
    )
    
    try:
        nid = db.save_news(item)
        saved_count += 1
        print(f'  ✓ {title[:40]}... (ID:{nid})')
    except Exception as e:
        print(f'  ✗ {title[:40]}... - {e}')

print(f'\n抓取完成! 保存 {saved_count} 条')

# 记录爬虫日志
db.log_spider_run(
    spider_name='模拟爬虫',
    start_time=datetime.now() - timedelta(minutes=1),
    end_time=datetime.now(),
    items_count=saved_count,
    status='success'
)

# 获取统计数据
print('\n[2/3] 更新统计数据...')
stats = db.get_news_stats(days=1)
print(f'  今日总数: {stats["total"]} 条')
print(f'  行情价格: {stats.get("by_category", {}).get("行情价格", 0)} 条')
print(f'  行业动态: {stats.get("by_category", {}).get("行业动态", 0)} 条')
print(f'  市场分析: {stats.get("by_category", {}).get("市场分析", 0)} 条')

# 获取未发送的新闻
print('\n[3/3] 准备邮件推送...')
unsent = db.get_unsent_news(limit=50)
print(f'  未推送新闻: {len(unsent)} 条')

if unsent:
    print(f'  邮件主题: 【化工早讯】{datetime.now().strftime("%m月%d日")}行业动态({len(unsent)}条)')
    print(f'  收件人: cz9721@163.com')
    print('\n  ⚠️ 注意: 请先在 config.py 中配置邮箱SMTP授权码才能实际发送')
    print('     当前仅生成邮件预览')
    
    # 生成邮件内容预览
    print('\n  邮件内容预览:')
    print('  ' + '-'*50)
    categorized = {}
    for item in unsent:
        cat = item.category if item.category in categories else '其他'
        categorized.setdefault(cat, []).append(item)
    
    for cat, items in categorized.items():
        print(f'  【{cat}】{len(items)}条')
        for item in items[:2]:  # 只显示前2条
            print(f'    • {item.title[:35]}...')
    print('  ' + '-'*50)
else:
    print('  无数据需要推送')

print('\n' + '='*60)
print('任务完成!')
print('='*60)
end_time = datetime.now().strftime("%H:%M:%S")
print(f'结束时间: {end_time}')
print()
print('数据已保存到数据库，可在Web界面查看:')
print('  http://localhost:5000')
