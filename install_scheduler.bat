@echo off
REM =============================================================
REM  注册 Windows 任务计划：每个交易日盘前 08:30 运行盘前报告。
REM  实际「交易日判断 + 报告生成 + 推送」逻辑见 run_daily.py，
REM  此处仅按 周一~周五 触发，run_daily.py 内部再做节假日跳过。
REM
REM  用法：右键「以管理员身份运行」本文件（普通用户也可，任务注册到当前用户库）。
REM  卸载：schtasks /Delete /TN "ChemInfoBot_Daily" /F
REM =============================================================

set "PYTHON=%~dp0venv\Scripts\python.exe"
set "SCRIPT=%~dp0run_daily.py"
set "TASKNAME=ChemInfoBot_Daily"

if not exist "%PYTHON%" (
    echo [错误] 找不到 venv 解释器：%PYTHON%
    echo        请先运行一次：python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo 正在注册任务计划：%TASKNAME%
schtasks /Create /TN "%TASKNAME%" ^
  /TR "\"%PYTHON%\" \"%SCRIPT%\"" ^
  /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 08:30 ^
  /RU "%USERNAME%" /F

if %ERRORLEVEL%==0 (
    echo.
    echo [成功] 任务计划已注册：%TASKNAME%
    echo         触发时间：周一~周五 08:30（run_daily.py 内部再做节假日判断）
    echo         查看：taskschd.msc -> 任务计划程序库 -> %TASKNAME%
) else (
    echo.
    echo [失败] 注册未成功，错误码 %ERRORLEVEL%。尝试用管理员身份运行本文件。
)
pause
