@echo off
cd /d D:\Backup\Documents\ChemInfoBot
python -c "from stock_mail_plugin import send_enhanced; send_enhanced()"
echo Done
