@echo off
chcp 65001 >nul
echo ========================================
echo   化工爬虫 - 自动运行管理工具
echo ========================================
echo.
echo 选择操作:
echo.
echo 1. 立即运行爬虫 (抓取数据)
echo 2. 立即发送邮件 (推送今日资讯)
echo 3. 启动定时调度器 (后台持续运行)
echo 4. 停止定时调度器
echo 5. 查看运行状态
echo 6. 查看今日数据
echo 7. 打开Web管理界面
echo 8. 退出
echo.
set /p choice=请输入选项 (1-8): 

cd /d "D:\Backup\Documents\ChemInfoBot"

if "%choice%"=="1" goto run_spider
if "%choice%"=="2" goto send_email
if "%choice%"=="3" goto start_scheduler
if "%choice%"=="4" goto stop_scheduler
if "%choice%"=="5" goto check_status
if "%choice%"=="6" goto today_data
if "%choice%"=="7" goto web_ui
if "%choice%"=="8" goto exit

echo 无效选项
goto end

:run_spider
echo.
echo [正在运行爬虫...]
python run_spider_simple.py
goto end

:send_email
echo.
echo [正在发送邮件...]
echo 注意: 需先在 config.py 中配置邮箱
goto end

:start_scheduler
echo.
echo [正在启动定时调度器...]
echo 调度器将在后台运行
echo 爬虫任务: 每2小时
echo 邮件推送: 每天 08:30
echo.
start /B python start_scheduler.py > scheduler.log 2>&1
echo 调度器已启动
echo 查看日志: type scheduler.log
goto end

:stop_scheduler
echo.
echo [正在停止调度器...]
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *scheduler*" 2>nul
taskkill /F /IM python.exe 2>nul
echo 调度器已停止
goto end

:check_status
echo.
echo [检查运行状态...]
python check_today_status.py
goto end

:today_data
echo.
echo [查看今日数据...]
python -c "from data_storage import db; from datetime import datetime; news = db.get_latest_news(hours=24, limit=10); print('今日最新资讯:'); [print(f'{i+1}. {n.title}') for i,n in enumerate(news)]"
goto end

:web_ui
echo.
echo [启动Web界面...]
echo 访问地址: http://localhost:5000
start python web_app.py
goto end

:exit
echo.
echo 再见!
exit /b 0

:end
echo.
pause
