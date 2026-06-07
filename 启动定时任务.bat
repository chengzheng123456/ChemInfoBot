@echo off
title 化工资讯爬虫 - 定时任务调度器
echo ==========================================
echo 化工行业信息爬虫工具
echo 定时任务调度器
echo ==========================================
echo.
echo 请选择运行模式:
echo.
echo 1. 后台模式 (持续运行)
echo 2. 立即运行一次爬虫
echo 3. 立即发送一次邮件
echo 4. 测试邮件配置
echo 5. 退出
echo.
python scheduler.py
pause
