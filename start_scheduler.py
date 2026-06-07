#!/usr/bin/env python
"""启动定时调度器 - 后台持续运行"""
import sys
import time
sys.path.insert(0, r'D:\Backup\Documents\ChemInfoBot')

from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import config

# 导入任务函数
from chem_spider import run_spider_job
from stock_mail_plugin import send_enhanced
from email_sender import send_daily_email
from data_storage import db

print('='*60)
print('化工爬虫 - 定时调度器')
print('='*60)
print(f'启动时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print()

# 创建调度器
scheduler = BackgroundScheduler(timezone=config.SCHEDULER_CONFIG['timezone'])

# 定义任务
def spider_job():
    """爬虫任务"""
    print(f'\n[{datetime.now().strftime("%H:%M:%S")}] 开始执行爬虫任务...')
    try:
        result = run_spider_job()
        print(f'  完成! 抓取: {result["total"]} 条')
    except Exception as e:
        print(f'  失败: {e}')

def email_job():
    """邮件推送任务"""
    print(f'\n[{datetime.now().strftime("%H:%M:%S")}] 开始执行邮件推送...')
    try:
        result = send_enhanced()
        if result:
            print('  邮件发送成功!')
        else:
            print('  无数据或发送失败')
    except Exception as e:
        print(f'  失败: {e}')

def cleanup_job():
    """数据清理任务"""
    print(f'\n[{datetime.now().strftime("%H:%M:%S")}] 开始执行数据清理...')
    try:
        deleted = db.delete_old_news(days=30)
        print(f'  清理完成! 删除 {deleted} 条旧数据')
    except Exception as e:
        print(f'  失败: {e}')

# 添加任务
# 爬虫任务 - 每2小时运行
scheduler.add_job(
    spider_job,
    'interval',
    hours=2,
    id='spider',
    name='化工信息爬虫',
    replace_existing=True
)
print('[✓] 爬虫任务已配置: 每2小时运行')

# 邮件推送任务 - 每天08:30
hour, minute = config.SCHEDULER_CONFIG['daily_push_time'].split(':')
scheduler.add_job(
    email_job,
    CronTrigger(hour=hour, minute=minute),
    id='email',
    name='每日邮件推送',
    replace_existing=True
)
print(f'[✓] 邮件推送已配置: 每天 {config.SCHEDULER_CONFIG["daily_push_time"]}')

# 数据清理任务 - 每周日02:00
scheduler.add_job(
    cleanup_job,
    CronTrigger(day_of_week='sun', hour=2, minute=0),
    id='cleanup',
    name='数据清理',
    replace_existing=True
)
print('[✓] 数据清理已配置: 每周日 02:00')

print()
print('='*60)
print('调度器已启动!')
print('='*60)
print()
print('任务列表:')
for job in scheduler.get_jobs():
    next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M') if job.next_run_time else 'N/A'
    print(f'  • {job.name}')
    print(f'    下次运行: {next_run}')
    print()

print('按 Ctrl+C 停止调度器')
print('='*60)

# 启动调度器
scheduler.start()

# 保持运行
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print('\n\n正在停止调度器...')
    scheduler.shutdown()
    print('调度器已停止')
    print('='*60)
