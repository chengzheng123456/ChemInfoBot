#!/usr/bin/env python
"""检查今日爬虫运行状态"""
import sys
sys.path.insert(0, r'D:\Backup\Documents\ChemInfoBot')

from data_storage import db
from datetime import datetime, timedelta

print('='*60)
print('化工爬虫 - 今日运行状态检查')
print('='*60)

# 获取今天的开始和结束时间
today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
tomorrow = today + timedelta(days=1)

print(f'\n查询日期: {today.strftime("%Y-%m-%d")}')
print(f'当前时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

# 获取今天的爬虫日志
logs = db.get_spider_logs(limit=100)
today_logs = []
for log in logs:
    try:
        start_time_str = log['start_time']
        if isinstance(start_time_str, str):
            start_time_str = start_time_str.replace('Z', '+00:00').replace(' ', 'T')
            log_start = datetime.fromisoformat(start_time_str)
            if today <= log_start < tomorrow:
                today_logs.append(log)
    except:
        pass

if today_logs:
    print(f'[✓] 今日共运行 {len(today_logs)} 次爬虫任务\n')
    for log in today_logs:
        try:
            start_str = log['start_time']
            end_str = log['end_time']
            
            if isinstance(start_str, str):
                start = datetime.fromisoformat(start_str.replace('Z', '+00:00').replace(' ', 'T'))
            else:
                start = start_str
                
            if end_str and isinstance(end_str, str):
                end = datetime.fromisoformat(end_str.replace('Z', '+00:00').replace(' ', 'T'))
            else:
                end = end_str
                
            duration = (end - start).total_seconds() if end else 0
            
            status_icon = '✓' if log['status'] == 'success' else '✗'
            print(f'{status_icon} {log["spider_name"]}')
            print(f'  时间: {start.strftime("%H:%M:%S")} - {end.strftime("%H:%M:%S") if end else "未完成"}')
            print(f'  耗时: {duration:.1f}秒')
            print(f'  抓取: {log["items_count"]} 条')
            print(f'  状态: {log["status"]}')
            if log['error_message']:
                print(f'  错误: {log["error_message"][:50]}')
            print()
        except Exception as e:
            print(f'  解析错误: {e}')
else:
    print('[✗] 今日暂无爬虫运行记录')
    print()

# 获取邮件发送记录
print('='*60)
print('邮件发送记录')
print('='*60)
print()

email_logs = db.get_email_logs(limit=50)
today_emails = []
for log in email_logs:
    try:
        send_time_str = log['send_time']
        if isinstance(send_time_str, str):
            send_time_str = send_time_str.replace('Z', '+00:00').replace(' ', 'T')
            log_send = datetime.fromisoformat(send_time_str)
            if today <= log_send < tomorrow:
                today_emails.append(log)
    except:
        pass

if today_emails:
    print(f'[✓] 今日已发送 {len(today_emails)} 次邮件\n')
    for log in today_emails:
        try:
            send_time_str = log['send_time']
            if isinstance(send_time_str, str):
                send_time = datetime.fromisoformat(send_time_str.replace('Z', '+00:00').replace(' ', 'T'))
            else:
                send_time = send_time_str
                
            status_icon = '✓' if log['status'] == 'success' else '✗'
            print(f'{status_icon} {send_time.strftime("%H:%M:%S")} - {log["subject"][:40]}...')
            print(f'  推送: {log["items_count"]} 条')
            print(f'  状态: {log["status"]}')
            print()
        except Exception as e:
            print(f'  解析错误: {e}')
else:
    print('[✗] 今日暂无邮件发送记录')
    print()

# 获取最新新闻统计
print('='*60)
print('今日数据更新情况')
print('='*60)
print()

stats = db.get_news_stats(days=1)
print(f'今日抓取新闻总数: {stats["total"]} 条')
print(f'行情价格: {stats.get("by_category", {}).get("行情价格", 0)} 条')
print(f'行业动态: {stats.get("by_category", {}).get("行业动态", 0)} 条')
print(f'市场分析: {stats.get("by_category", {}).get("市场分析", 0)} 条')
print(f'政策法规: {stats.get("by_category", {}).get("政策法规", 0)} 条')

sources = stats.get("by_source", {})
print(f'数据来源: {", ".join(sources.keys()) if sources else "无"}')

print()
print('='*60)
