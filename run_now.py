#!/usr/bin/env python
"""立即运行爬虫和邮件发送"""
import sys
sys.path.insert(0, r'D:\Backup\Documents\ChemInfoBot')

from chem_spider import run_spider_job
from email_sender import send_daily_email
from datetime import datetime

print('='*60)
print('立即启动爬虫任务')
print('='*60)
start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f'开始时间: {start_time}')
print()

# 运行爬虫
print('正在抓取化工行业数据...')
result = run_spider_job()

print(f'\n爬虫完成!')
print(f'  - 抓取总数: {result["total"]} 条')
print(f'  - 保存成功: {result["saved_count"]} 条')
if result.get('errors'):
    print(f'  - 错误数: {len(result["errors"])} 个')

# 发送邮件
print('\n' + '='*60)
print('立即发送邮件')
print('='*60)
email_result = send_daily_email()

if email_result:
    print('邮件发送成功!')
else:
    print('邮件发送失败或无数据可发送')

print('\n' + '='*60)
print('任务完成!')
print('='*60)
end_time = datetime.now().strftime("%H:%M:%S")
print(f'结束时间: {end_time}')
