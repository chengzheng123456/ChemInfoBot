# 化工行业信息爬虫工具 (ChemInfoBot)

一款自动化化工行业信息采集与推送系统，支持定时抓取化工新闻、价格行情，并通过邮件推送。

## 功能特性

- **定时抓取**：自动从多个化工行业网站抓取最新信息
- **智能分类**：行情价格、行业动态、市场分析自动分类
- **邮件推送**：每天早上8:30自动推送至指定邮箱
- **Web管理**：可视化查看历史数据和配置管理
- **数据持久化**：SQLite数据库存储，支持历史查询

## 支持的数据源

- 百川盈孚 (baichuan.com) - 价格行情
- 中国化工网 (chemnet.com.cn) - 行业新闻
- 隆众资讯 (oilchem.net) - 市场分析

## 快速启动

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置邮箱：
编辑 `config.py`，填写163邮箱的SMTP授权码

3. 启动系统：
```bash
# 启动Web管理界面（默认 http://localhost:5000）
python web_app.py

# 手动运行一次爬虫测试
python chem_spider.py

# 启动定时调度器（后台运行）
python scheduler.py
```

## 文件说明

- `chem_spider.py` - 核心爬虫模块
- `data_storage.py` - 数据存储模块（SQLite）
- `email_sender.py` - 邮件发送模块
- `scheduler.py` - 定时任务调度器
- `web_app.py` - Flask Web管理界面
- `config.py` - 全局配置文件
- `requirements.txt` - 依赖清单

## 技术栈

- Python 3.9+
- Flask + Bootstrap 5 (Web界面)
- APScheduler (定时任务)
- SQLite (数据存储)
- requests + BeautifulSoup4 (爬虫)

## 系统要求

- Windows 10/11 或 macOS/Linux
- Python 3.9 或更高版本
- 网络连接

---

**作者**: ChemInfoBot  
**版本**: 1.0.0  
**更新日期**: 2025-05-30


## 环境配置

1. 复制 config.py.example 为 config.py
2. 填写你的邮箱 SMTP 授权码、飞书 Webhook、PushPlus Token
3. 运行 pip install -r requirements.txt
