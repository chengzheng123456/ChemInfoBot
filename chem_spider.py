"""
化工行业信息爬虫工具 - 核心爬虫模块
支持多个数据源，使用requests+BeautifulSoup4实现
"""

import re
import os
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import config
from data_storage import ChemNewsItem, db

def _setup_logger():
    logger = logging.getLogger(__name__)
    if logger.handlers: return logger
    handlers = [logging.StreamHandler()]
    try:
        d = os.path.dirname(config.LOG_CONFIG["file"])
        os.makedirs(d, exist_ok=True)
        handlers.append(logging.FileHandler(config.LOG_CONFIG["file"], encoding="utf-8"))
    except: pass
    logging.basicConfig(level=config.LOG_CONFIG["level"],format=config.LOG_CONFIG["format"],handlers=handlers,force=True)
logger = logging.getLogger(__name__)


class ChemSpider:
    """化工行业信息爬虫基类"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.SPIDER_CONFIG['user_agent'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        self.timeout = config.SPIDER_CONFIG['request_timeout']
        self.retry_times = config.SPIDER_CONFIG['retry_times']
        self.retry_delay = config.SPIDER_CONFIG['retry_delay']
        self.delay = config.SPIDER_CONFIG['delay_between_requests']
    
    def _fetch(self, url: str, **kwargs) -> Optional[str]:
        """带重试机制的请求方法"""
        for attempt in range(self.retry_times):
            try:
                time.sleep(self.delay)
                response = self.session.get(
                    url, 
                    timeout=self.timeout,
                    **kwargs
                )
                response.raise_for_status()
                response.encoding = response.apparent_encoding or 'utf-8'
                return response.text
            except Exception as e:
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.retry_times}): {url} - {e}")
                if attempt < self.retry_times - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    logger.error(f"请求最终失败: {url}")
                    return None
        return None
    
    def _classify_category(self, title: str, content: str) -> str:
        """自动分类新闻"""
        text = f"{title} {content}"
        category_scores = {}
        
        for category, keywords in config.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                category_scores[category] = score
        
        if category_scores:
            return max(category_scores, key=category_scores.get)
        return "其他"
    
    def _extract_keywords(self, title: str, content: str) -> str:
        """提取相关化工产品关键词"""
        text = f"{title} {content}"
        found = [p for p in config.CHEM_PRODUCTS if p in text]
        return ",".join(set(found)) if found else ""
    
    def _generate_summary(self, content: str, max_length: int = 200) -> str:
        """生成摘要"""
        if len(content) <= max_length:
            return content
        return content[:max_length].rsplit('。', 1)[0] + '。'
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析各种日期格式"""
        patterns = [
            (r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})', '%Y-%m-%d %H:%M'),
            (r'(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{1,2})', '%Y/%m/%d %H:%M'),
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', '%Y-%m-%d'),
            (r'(\d{4})/(\d{1,2})/(\d{1,2})', '%Y/%m/%d'),
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日', '%Y年%m月%d日'),
        ]
        
        for pattern, fmt in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    return datetime.strptime(match.group(0), fmt)
                except ValueError:
                    continue
        
        return datetime.now()


class ChemnetSpider(ChemSpider):
    """中国化工网爬虫"""
    
    name = "中国化工网"
    base_url = "https://www.chemnet.com.cn"
    
    def fetch_news(self) -> List[ChemNewsItem]:
        """抓取中国化工网新闻"""
        items = []
        
        # 新闻中心
        news_url = "https://www.chemnet.com.cn/news/"
        html = self._fetch(news_url)
        
        if html:
            soup = BeautifulSoup(html, 'lxml')
            news_list = soup.select('.list-item, .news-item, .list li')
            
            for item in news_list[:20]:  # 限制数量
                try:
                    link = item.find('a')
                    if not link:
                        continue
                    
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    if not href.startswith('http'):
                        href = urljoin(self.base_url, href)
                    
                    # 获取详情内容
                    content = self._fetch_detail(href)
                    
                    # 获取日期
                    date_elem = item.select_one('.date, .time, .pubdate')
                    date_str = date_elem.get_text(strip=True) if date_elem else ""
                    publish_date = self._parse_date(date_str) if date_str else datetime.now()
                    
                    # 只抓取24小时内的
                    if datetime.now() - publish_date > timedelta(days=1):
                        continue
                    
                    news_item = ChemNewsItem(
                        title=title,
                        content=content,
                        source=self.name,
                        source_url=href,
                        category=self._classify_category(title, content),
                        publish_date=publish_date,
                        keywords=self._extract_keywords(title, content),
                        summary=self._generate_summary(content),
                    )
                    items.append(news_item)
                    
                except Exception as e:
                    logger.error(f"解析新闻项失败: {e}")
                    continue
        
        logger.info(f"{self.name} 抓取完成，共 {len(items)} 条")
        return items
    
    def _fetch_detail(self, url: str) -> str:
        """获取详情页内容"""
        html = self._fetch(url)
        if not html:
            return ""
        
        soup = BeautifulSoup(html, 'lxml')
        
        # 尝试多种选择器
        selectors = [
            '.content-detail', '.article-content', '.news-content',
            '#content', '.detail-content', 'article',
            '.text-content', '.main-content'
        ]
        
        for selector in selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                text = content_elem.get_text(separator=' ', strip=True)
                return re.sub(r'\s+', ' ', text)
        
        return ""


class OilchemSpider(ChemSpider):
    """隆众资讯爬虫"""
    
    name = "隆众资讯"
    base_url = "https://www.oilchem.net"
    
    def fetch_news(self) -> List[ChemNewsItem]:
        """抓取隆众资讯数据"""
        items = []
        
        # 资讯中心
        urls_to_fetch = [
            "https://www.oilchem.net/news/",
            "https://www.oilchem.net/price/",
        ]
        
        for url in urls_to_fetch:
            html = self._fetch(url)
            if not html:
                continue
            
            soup = BeautifulSoup(html, 'lxml')
            news_list = soup.select('.news-list li, .list-item, .info-item')
            
            for item in news_list[:15]:
                try:
                    link = item.find('a')
                    if not link:
                        continue
                    
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    if not href.startswith('http'):
                        href = urljoin(self.base_url, href)
                    
                    content = self._fetch_detail(href)
                    
                    date_elem = item.select_one('.date, .time, .pubdate')
                    date_str = date_elem.get_text(strip=True) if date_elem else ""
                    publish_date = self._parse_date(date_str) if date_str else datetime.now()
                    
                    if datetime.now() - publish_date > timedelta(days=1):
                        continue
                    
                    news_item = ChemNewsItem(
                        title=title,
                        content=content,
                        source=self.name,
                        source_url=href,
                        category=self._classify_category(title, content),
                        publish_date=publish_date,
                        keywords=self._extract_keywords(title, content),
                        summary=self._generate_summary(content),
                    )
                    items.append(news_item)
                    
                except Exception as e:
                    logger.error(f"解析失败: {e}")
                    continue
        
        logger.info(f"{self.name} 抓取完成，共 {len(items)} 条")
        return items
    
    def _fetch_detail(self, url: str) -> str:
        """获取详情页"""
        html = self._fetch(url)
        if not html:
            return ""
        
        soup = BeautifulSoup(html, 'lxml')
        
        selectors = [
            '.article-content', '.detail-content', '.news-detail',
            '#content', '.content', 'article'
        ]
        
        for selector in selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                text = content_elem.get_text(separator=' ', strip=True)
                return re.sub(r'\s+', ' ', text)
        
        return ""


class CnfeolSpider(ChemSpider):
    """中国铁合金在线爬虫"""
    
    name = "中国铁合金在线"
    base_url = "https://www.cnfeol.com"
    
    def fetch_news(self) -> List[ChemNewsItem]:
        """抓取铁合金在线数据"""
        items = []
        
        # 市场动态
        url = "https://www.cnfeol.com/news/"
        html = self._fetch(url)
        
        if html:
            soup = BeautifulSoup(html, 'lxml')
            news_list = soup.select('.news-item, .list-item, .nlist li')
            
            for item in news_list[:15]:
                try:
                    link = item.find('a')
                    if not link:
                        continue
                    
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    if not href.startswith('http'):
                        href = urljoin(self.base_url, href)
                    
                    content = self._fetch_detail(href)
                    
                    date_elem = item.select_one('.date, .time')
                    date_str = date_elem.get_text(strip=True) if date_elem else ""
                    publish_date = self._parse_date(date_str) if date_str else datetime.now()
                    
                    if datetime.now() - publish_date > timedelta(days=1):
                        continue
                    
                    news_item = ChemNewsItem(
                        title=title,
                        content=content,
                        source=self.name,
                        source_url=href,
                        category=self._classify_category(title, content),
                        publish_date=publish_date,
                        keywords=self._extract_keywords(title, content),
                        summary=self._generate_summary(content),
                    )
                    items.append(news_item)
                    
                except Exception as e:
                    logger.error(f"解析失败: {e}")
                    continue
        
        logger.info(f"{self.name} 抓取完成，共 {len(items)} 条")
        return items
    
    def _fetch_detail(self, url: str) -> str:
        """获取详情页"""
        html = self._fetch(url)
        if not html:
            return ""
        
        soup = BeautifulSoup(html, 'lxml')
        
        selectors = [
            '.content-detail', '.article-body', '.news-content',
            '.detail', '#content', 'article'
        ]
        
        for selector in selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                text = content_elem.get_text(separator=' ', strip=True)
                return re.sub(r'\s+', ' ', text)
        
        return ""


class SpiderManager:
    """Coordinator for all spiders"""
    def __init__(self):
        from a_stock_spider import AStockSpider, MarketNewsSpider
        self.spiders = [ChemnetSpider(),OilchemSpider(),CnfeolSpider(),AStockSpider()]
        self.news_spiders = [MarketNewsSpider()]
    def run_all(self):
        results = {"total":0,"by_source":{},"errors":[],"start_time":datetime.now()}
        all_items = []
        for spider in self.spiders:
            sn = spider.name;st = datetime.now()
            try:
                items = spider.fetch_news()
                results["by_source"][sn] = len(items)
                results["total"] += len(items)
                all_items.extend(items)
                db.log_spider_run(sn,st,datetime.now(),len(items),"success")
            except Exception as e:
                db.log_spider_run(sn,st,datetime.now(),0,"failed",str(e))
                logger.error(f"{sn} failed: {e}")
                results["errors"].append({"spider":sn,"error":str(e)})
        saved = 0
        for item in all_items:
            try: db.save_news(item);saved+=1
            except: pass
        results["saved_count"] = saved
        results["end_time"] = datetime.now()
        if results["total"] == 0:
            logger.critical("ALL SOURCES EMPTY - check connectivity")
            results["all_empty"] = True
        try:
            stock = self.spiders[-1]
            if hasattr(stock,"fetch_sector_rankings"):
                results["stock_sectors"] = stock.fetch_sector_rankings(3)
        except Exception as e:
            logger.error(f"Stock data failed: {e}")
        all_market_news = []
        for ns in self.news_spiders:
            try: all_market_news.extend(ns.fetch_news())
            except: pass
        results["market_news"] = all_market_news[:30]
        logger.info(f"Done: {results["total"]} items, {saved} saved")
        return results

spider_manager = SpiderManager()

def run_spider_job():
    """定时爬虫任务入口"""
    logger.info("=" * 50)
    logger.info("开始执行定时爬虫任务")
    logger.info("=" * 50)
    
    results = spider_manager.run_all()
    
    logger.info(f"任务完成! 总抓取: {results['total']}, 保存: {results['saved_count']}")
    if results['errors']:
        logger.warning(f"错误数量: {len(results['errors'])}")
    
    return results


if __name__ == "__main__":
    # 测试运行
    print("测试爬虫...")
    results = run_spider_job()
    print(f"\n抓取结果: {results}")
