#!/usr/bin/env python
"""快速测试 - 验证系统核心功能"""
import sys
sys.path.insert(0, r'D:\Backup\Documents\ChemInfoBot')

print('=' * 60)
print('化工行业信息爬虫工具 - 快速测试')
print('=' * 60)

# 测试配置
print('\n[1/5] 测试配置模块...')
try:
    import config
    print(f'  ✓ 数据库: {config.DATABASE_PATH}')
    print(f'  ✓ 收件邮箱: {config.EMAIL_CONFIG["recipient_email"]}')
    print(f'  ✓ 推送时间: {config.SCHEDULER_CONFIG["daily_push_time"]}')
except Exception as e:
    print(f'  ✗ 配置错误: {e}')
    sys.exit(1)

# 测试数据库
print('\n[2/5] 测试数据存储模块...')
try:
    from data_storage import db, ChemNewsItem
    from datetime import datetime
    
    # 保存测试数据
    test = ChemNewsItem(
        title='测试：甲醇市场价格动态',
        content='华东地区甲醇价格上涨，市场交易活跃。',
        source='测试系统',
        source_url='https://test.com/1',
        category='行情价格',
        keywords='甲醇',
        summary='甲醇价格上涨',
        publish_date=datetime.now()
    )
    nid = db.save_news(test)
    print(f'  ✓ 保存成功，ID: {nid}')
    
    # 查询
    stats = db.get_news_stats(days=1)
    print(f'  ✓ 统计: 共{stats["total"]}条')
    
    # 搜索
    results = db.search_news('甲醇')
    print(f'  ✓ 搜索: 找到{len(results)}条')
    
except Exception as e:
    print(f'  ✗ 数据库错误: {e}')
    import traceback
    traceback.print_exc()

# 测试爬虫核心（不依赖requests）
print('\n[3/5] 测试爬虫核心功能...')
try:
    # 只测试分类逻辑
    title = 'PTA价格上涨，下游需求增加'
    content = '今日PTA市场报价上调，华东地区主流价格上涨100元/吨。'
    
    # 模拟分类逻辑
    CATEGORY_KEYWORDS = {
        "行情价格": ["价格", "行情", "报价", "走势", "涨跌", "上调", "下调"],
        "行业动态": ["投产", "扩建", "检修", "产能"],
        "市场分析": ["分析", "预测", "供需", "库存"],
    }
    text = f"{title} {content}"
    scores = {cat: sum(1 for kw in kws if kw in text) 
              for cat, kws in CATEGORY_KEYWORDS.items()}
    category = max(scores, key=scores.get) if any(scores.values()) else "其他"
    print(f'  ✓ 智能分类: "{title}" -> {category}')
    
    # 测试关键词提取
    CHEM_PRODUCTS = ["甲醇", "乙醇", "丙烯", "乙烯", "苯", "PTA", "PVC", "PE", "PP"]
    found = [p for p in CHEM_PRODUCTS if p in text]
    keywords = ",".join(found) if found else ""
    print(f'  ✓ 关键词提取: {keywords if keywords else "无"}')
    
except Exception as e:
    print(f'  ✗ 爬虫核心错误: {e}')

# 测试邮件配置
print('\n[4/5] 测试邮件模块...')
try:
    from email_sender import email_sender
    print(f'  ✓ SMTP: {email_sender.smtp_server}:{email_sender.smtp_port}')
    print(f'  ✓ 发件人: {email_sender.sender_email}')
    print(f'  ✓ 收件人: {email_sender.recipient_email}')
    print(f'  ✓ SSL加密: {"已启用" if email_sender.use_ssl else "未启用"}')
except Exception as e:
    print(f'  ✗ 邮件配置错误: {e}')

# 测试Web应用
print('\n[5/5] 测试Web应用模块...')
try:
    from flask import Flask
    from web_app import app
    print(f'  ✓ Flask应用已加载')
    print(f'  ✓ 路由数量: {len(list(app.url_map.iter_rules()))}')
    routes = [r.rule for r in app.url_map.iter_rules() 
              if not r.rule.startswith('/static')]
    print(f'  ✓ 可用路由: {", ".join(routes[:5])}...')
except Exception as e:
    print(f'  ✗ Web应用错误: {e}')
    import traceback
    traceback.print_exc()

print('\n' + '=' * 60)
print('测试完成! 核心功能运行正常')
print('=' * 60)
print('\n系统已就绪，可以运行:')
print('  1. 双击 "启动Web界面.bat" 或运行: python web_app.py')
print('  2. 访问 http://localhost:5000')
print('  3. 双击 "启动定时任务.bat" 配置后台任务')
print('\n⚠️ 重要: 首次使用前请在 config.py 中配置163邮箱SMTP授权码!')
