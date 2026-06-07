"""
化工行业信息爬虫工具 - 定时任务调度器
支持每日定时抓取和邮件推送
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

import config
from chem_spider import run_spider_job
from stock_mail_plugin import send_enhanced
from email_sender import send_daily_email

# 配置日志
import os
def _setup_logger():
    log = logging.getLogger(__name__)
    if log.handlers: return log
    h = [logging.StreamHandler()]
    try:
        d = os.path.dirname(config.LOG_CONFIG["file"])
        os.makedirs(d, exist_ok=True)
        h.append(logging.FileHandler(config.LOG_CONFIG["file"], encoding="utf-8"))
    except:
        pass
    logging.basicConfig(level=config.LOG_CONFIG["level"], format=config.LOG_CONFIG["format"], handlers=h, force=True)
    return log
logger = _setup_logger()


class ChemScheduler:
    """化工信息爬虫定时调度器"""
    
    def __init__(self):
        self.scheduler = BackgroundScheduler(
            timezone=config.SCHEDULER_CONFIG['timezone']
        )
        self.running = False
        self._setup_listeners()
    
    def _setup_listeners(self):
        """设置事件监听器"""
        self.scheduler.add_listener(
            self._on_job_executed,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._on_job_error,
            EVENT_JOB_ERROR
        )
    
    def _on_job_executed(self, event):
        """任务执行完成回调"""
        logger.info(f"任务完成: {event.job_id}")
    
    def _on_job_error(self, event):
        """任务执行出错回调"""
        logger.error(f"任务出错: {event.job_id} - {event.exception}")
    
    def _spider_job(self):
        """爬虫任务"""
        logger.info("-" * 50)
        logger.info("调度器触发爬虫任务")
        logger.info("-" * 50)
        
        try:
            result = run_spider_job()
            logger.info(f"爬虫任务完成: 共抓取 {result['total']} 条")
        except Exception as e:
            logger.error(f"爬虫任务失败: {e}")
    
    def _email_job(self):
        """Comprehensive A-share report email"""
        logger.info("-" * 50)
        logger.info("Scheduler triggering comprehensive A-share report")
        logger.info("-" * 50)
        try:
            result = send_enhanced()
            if result:
                logger.info("Comprehensive A-share report email sent")
            else:
                logger.info("No A-share data, using standard email")
                result = send_daily_email()
        except Exception as e:
            logger.error(f"Comprehensive email failed: {e}")
    
    def setup_jobs(self):
        """设置定时任务"""
        # 爬虫任务 - 每2小时运行一次
        self.scheduler.add_job(
            self._spider_job,
            trigger='interval',
            hours=2,
            id='spider_job',
            name='化工信息爬虫',
            replace_existing=True
        )
        logger.info("已设置爬虫任务: 每2小时运行一次")
        
        # 邮件推送任务 - 每天早上8:30
        hour, minute = config.SCHEDULER_CONFIG['daily_push_time'].split(':')
        self.scheduler.add_job(
            self._email_job,
            trigger=CronTrigger(
                hour=hour,
                minute=minute
            ),
            id='email_job',
            name='每日邮件推送',
            replace_existing=True
        )
        logger.info(f"已设置邮件推送任务: 每天 {config.SCHEDULER_CONFIG['daily_push_time']}")
        
        # 数据清理任务 - 每周日凌晨2点运行
        self.scheduler.add_job(
            self._cleanup_job,
            trigger=CronTrigger(
                day_of_week='sun',
                hour=2,
                minute=0
            ),
            id='cleanup_job',
            name='数据清理',
            replace_existing=True
        )
        logger.info("已设置数据清理任务: 每周日凌晨2点")
    
    def _cleanup_job(self):
        """数据清理任务"""
        logger.info("开始数据清理任务...")
        
        try:
            from data_storage import db
            deleted_count = db.delete_old_news(days=30)
            logger.info(f"数据清理完成: 删除了 {deleted_count} 条旧数据")
        except Exception as e:
            logger.error(f"数据清理失败: {e}")
    
    def start(self):
        """启动调度器"""
        self.setup_jobs()
        self.scheduler.start()
        self.running = True
        
        logger.info("=" * 60)
        logger.info("化工信息爬虫调度器已启动")
        logger.info(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        logger.info("已配置任务:")
        for job in self.scheduler.get_jobs():
            logger.info(f"  - {job.name}: {job.trigger}")
        logger.info("=" * 60)
    
    def stop(self):
        """停止调度器"""
        if self.running:
            self.scheduler.shutdown()
            self.running = False
            logger.info("调度器已停止")
    
    def get_status(self) -> dict:
        """获取调度器状态"""
        return {
            'running': self.running,
            'jobs': [
                {
                    'id': job.id,
                    'name': job.name,
                    'next_run_time': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else None,
                    'trigger': str(job.trigger)
                }
                for job in self.scheduler.get_jobs()
            ]
        }
    
    def run_job_now(self, job_id: str) -> bool:
        """立即执行指定任务"""
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                self.scheduler.modify_job(job_id, next_run_time=datetime.now())
                logger.info(f"已触发任务立即执行: {job_id}")
                return True
            else:
                logger.warning(f"任务不存在: {job_id}")
                return False
        except Exception as e:
            logger.error(f"立即执行任务失败: {e}")
            return False


# 全局调度器实例
scheduler = ChemScheduler()


def signal_handler(signum, frame):
    """信号处理 - 优雅关闭"""
    logger.info("\n接收到关闭信号，正在停止调度器...")
    scheduler.stop()
    sys.exit(0)


def run_as_daemon():
    """以后台模式运行调度器"""
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Windows下没有SIGTERM，用SIGBREAK代替
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, signal_handler)
    
    scheduler.start()
    
    try:
        # 保持程序运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n用户中断，正在停止...")
        scheduler.stop()


def main():
    """主函数"""
    print("=" * 60)
    print("化工行业信息爬虫 - 定时任务调度器")
    print("=" * 60)
    print()
    print("选择运行模式:")
    print("1. 后台模式 (持续运行)")
    print("2. 立即运行一次爬虫任务")
    print("3. 立即运行一次邮件推送")
    print("4. 测试邮件配置")
    print("5. 退出")
    print()
    
    choice = input("请输入选项 (1-5): ").strip()
    
    if choice == "1":
        print("\n启动后台模式...")
        print("按 Ctrl+C 停止")
        run_as_daemon()
    
    elif choice == "2":
        print("\n立即运行爬虫任务...")
        run_spider_job()
    
    elif choice == "3":
        print("\n立即运行邮件推送...")
        send_enhanced()
    
    elif choice == "4":
        print("\n测试邮件配置...")
        from email_sender import test_email
        test_email()
    
    elif choice == "5":
        print("\n再见！")
        sys.exit(0)
    
    else:
        print("\n无效选项，请重新运行")


if __name__ == "__main__":
    main()
