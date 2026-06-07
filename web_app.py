"""
化工行业信息爬虫工具 - Web管理界面
使用Flask + Bootstrap 5构建
"""

import os
import json
from datetime import datetime, timedelta
from typing import Any

from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_bootstrap import Bootstrap

import config
from data_storage import db, ChemNewsItem
from chem_spider import spider_manager, run_spider_job
from email_sender import email_sender, send_daily_email
from scheduler import scheduler

# 创建Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = config.WEB_CONFIG['secret_key']
Bootstrap(app)


@app.route('/')
def index():
    """首页 - 仪表板"""
    # 获取统计数据
    stats = db.get_news_stats(days=7)
    
    # 获取最新新闻
    latest_news = db.get_latest_news(hours=24, limit=10)
    
    # 获取爬虫日志
    spider_logs = db.get_spider_logs(limit=5)
    
    # 获取邮件日志
    email_logs = db.get_email_logs(limit=5)
    
    return render_template('index.html',
                         stats=stats,
                         latest_news=latest_news,
                         spider_logs=spider_logs,
                         email_logs=email_logs)


@app.route('/news')
def news_list():
    """新闻列表页"""
    # 获取筛选参数
    category = request.args.get('category', '')
    keyword = request.args.get('keyword', '')
    days = int(request.args.get('days', 7))
    
    if keyword:
        news_items = db.search_news(keyword, category, limit=100)
    else:
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        news_items = db.get_news_by_date_range(
            start_time, end_time, category, limit=100
        )
    
    return render_template('news.html',
                         news_items=news_items,
                         category=category,
                         keyword=keyword,
                         days=days)


@app.route('/news/<int:news_id>')
def news_detail(news_id):
    """新闻详情页"""
    item = db.get_news_by_id(news_id)
    if not item:
        return "新闻不存在", 404
    
    return render_template('detail.html', item=item)


@app.route('/api/news/<int:news_id>')
def api_news_detail(news_id):
    """API: 获取新闻详情"""
    item = db.get_news_by_id(news_id)
    if item:
        return jsonify(item.to_dict())
    return jsonify({'error': 'Not found'}), 404


@app.route('/api/stats')
def api_stats():
    """API: 获取统计数据"""
    days = int(request.args.get('days', 7))
    stats = db.get_news_stats(days=days)
    return jsonify(stats)


@app.route('/api/news')
def api_news():
    """API: 获取新闻列表"""
    category = request.args.get('category')
    hours = int(request.args.get('hours', 24))
    limit = int(request.args.get('limit', 50))
    
    news_items = db.get_latest_news(
        hours=hours,
        category=category,
        limit=limit
    )
    
    return jsonify([item.to_dict() for item in news_items])


@app.route('/api/run_spider', methods=['POST'])
def api_run_spider():
    """API: 手动运行爬虫"""
    try:
        result = run_spider_job()
        return jsonify({
            'success': True,
            'message': f'爬虫完成，共抓取 {result["total"]} 条，保存 {result["saved_count"]} 条',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'爬虫失败: {str(e)}'
        }), 500


@app.route('/api/send_email', methods=['POST'])
def api_send_email():
    """API: 手动发送邮件"""
    try:
        result = send_daily_email()
        if result:
            return jsonify({
                'success': True,
                'message': '邮件发送成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '邮件发送失败或无数据'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'邮件发送失败: {str(e)}'
        }), 500


@app.route('/api/test_email', methods=['POST'])
def api_test_email():
    """API: 测试邮件配置"""
    try:
        if email_sender.test_connection():
            return jsonify({
                'success': True,
                'message': '邮件配置测试成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '邮件配置测试失败'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'测试失败: {str(e)}'
        }), 500


@app.route('/logs')
def logs():
    """日志查看页"""
    spider_logs = db.get_spider_logs(limit=50)
    email_logs = db.get_email_logs(limit=50)
    
    return render_template('logs.html',
                         spider_logs=spider_logs,
                         email_logs=email_logs)


@app.route('/settings')
def settings():
    """设置页"""
    return render_template('settings.html',
                         email_config=config.EMAIL_CONFIG,
                         spider_config=config.SPIDER_CONFIG,
                         scheduler_config=config.SCHEDULER_CONFIG)


@app.route('/about')
def about():
    """关于页"""
    return render_template('about.html')


# 错误处理
@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', 
                         error_code=404, 
                         error_message='页面未找到'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html',
                         error_code=500,
                         error_message='服务器内部错误'), 500


def run_app(host: str = None, port: int = None, debug: bool = None):
    """运行Web应用"""
    app.run(
        host=host or config.WEB_CONFIG['host'],
        port=port or config.WEB_CONFIG['port'],
        debug=debug if debug is not None else config.WEB_CONFIG['debug']
    )


if __name__ == '__main__':
    print("=" * 60)
    print("化工行业信息爬虫 - Web管理界面")
    print("=" * 60)
    print(f"访问地址: http://localhost:{config.WEB_CONFIG['port']}")
    print("=" * 60)
    print()
    
    run_app()
