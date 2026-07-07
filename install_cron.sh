#!/bin/sh
# =============================================================
#  Linux / macOS 定时调度参考（cron）。
#  交易日判断与推送逻辑在 run_daily.py 内；此处仅按 周一~周五 触发。
#
#  用法：
#    1) 编辑 crontab：  crontab -e
#    2) 追加下面一行（按需修改路径），保存退出即可：
#
#    30 8 * * 1-5 /ABS/PATH/TO/ChemInfoBot/venv/bin/python /ABS/PATH/TO/ChemInfoBot/run_daily.py >> /ABS/PATH/TO/ChemInfoBot/cron.log 2>&1
#
#  说明：
#    - 30 8      -> 每天 08:30
#    - * * 1-5   -> 周一至周五
#    - 日志追加到 cron.log，便于排错
# =============================================================
echo "将下面这行加入 crontab（crontab -e）后保存："
echo ""
echo "30 8 * * 1-5 $(pwd)/venv/bin/python $(pwd)/run_daily.py >> $(pwd)/cron.log 2>&1"
echo ""
