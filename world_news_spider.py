# 国际财经新闻抓取（纯 RSS，零注册、零 key、零第三方依赖）
# 阶段补充：把国际要闻并入"市场要闻"，让盘前报告与 AI 研判覆盖国际面（对 A 股的影响）。
# 设计：仅用标准库 urllib + xml.etree 解析；多源容错；单源失败跳过；全部失败返回 []（不编造）。
import logging
import re
import time
import random
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import xml.etree.ElementTree as ET

import config

logger = logging.getLogger(__name__)

# 默认国际财经 RSS 源（公开、稳定）。可在 config.WORLD_NEWS_CONFIG["sources"] 覆盖。
DEFAULT_SOURCES = [
    {"name": "BBC Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"name": "CNBC", "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=2&id=100003114"},
    {"name": "MarketWatch", "url": "https://feeds.marketwatch.com/marketwatch/topstories/"},
    {"name": "AP News", "url": "https://feeds.apnews.com/rss/apf-topnews"},
    {"name": "The Economist", "url": "https://www.economist.com/finance-and-economics/rss.xml"},
]

# A 股相关国际面关键词（命中优先；未命中则补足最新）
KEYWORDS = [
    "china", "chinese", "beijing", "shanghai", "hong kong", "csi", "a-share", "a share",
    "yuan", "renminbi", "fed", "federal reserve", "interest rate", "inflation",
    "tariff", "trade", "sanction", "oil", "crude", "opec", "commodit", "stock", "stocks",
    "wall street", "nasdaq", "dow", "s&p", "earnings", "gdp", "recession", "dollar",
    "treasury", "yield", "geopolit", "supply chain", "semiconduct",
    "芯片", "中国", "人民币", "美联储", "关税", "贸易", "原油", "股市", "通胀", "利率",
]

UA = {"User-Agent": "Mozilla/5.0 (compatible; ChemInfoBot/1.0; +https://github.com/chengzheng123456/ChemInfoBot)"}


def _local(tag):
    return tag.split('}')[-1] if '}' in tag else tag


def _text_of(elem, *names):
    for child in elem.iter():
        if _local(child.tag) in names:
            t = (child.text or "").strip()
            if t:
                return t
    return ""


def _link_of(elem):
    # RSS: <link>url</link> ；Atom: <link href="url"/>
    for child in elem:
        if _local(child.tag) == "link":
            if child.text and child.text.strip():
                return child.text.strip()
            href = child.get("href")
            if href:
                return href
    for child in elem.iter():
        if _local(child.tag) == "link":
            href = child.get("href")
            if href:
                return href
    return ""


def _clean(html):
    if not html:
        return ""
    txt = re.sub(r"<[^>]+>", "", html)
    txt = re.sub(r"&[a-zA-Z]+;", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:200]


def _parse_feed(text):
    """解析 RSS 2.0 与 Atom，返回 item/entry 列表（dict）。失败返回 []。"""
    try:
        root = ET.fromstring(text)
    except Exception as e:
        logger.warning("RSS parse error: %s", e)
        return []
    items = []
    for elem in root.iter():
        if _local(elem.tag) in ("item", "entry"):
            title = _text_of(elem, "title")
            link = _link_of(elem)
            desc = _clean(_text_of(elem, "description", "summary", "content"))
            pub = _text_of(elem, "pubDate", "updated", "published")
            if title and link:
                items.append({"title": title, "url": link, "summary": desc, "time": pub})
    return items


def _score(item):
    t = (item.get("title", "") + " " + item.get("summary", "")).lower()
    return sum(1 for k in KEYWORDS if k in t)


class WorldNewsSpider:
    name = "国际财经要闻 (RSS)"

    def _fetch(self, url):
        try:
            req = Request(url, headers=UA)
            with urlopen(req, timeout=20) as resp:
                raw = resp.read()
            return raw.decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning("World news fetch failed (%s): %s", url, e)
            return None

    def fetch_news(self, max_items=None):
        """抓取国际财经 RSS；失败/无内容返回 []（不编造）。"""
        cfg = getattr(config, "WORLD_NEWS_CONFIG", None) or {}
        if cfg.get("enabled", True) is False:
            return []
        sources = cfg.get("sources") or DEFAULT_SOURCES
        max_items = max_items or cfg.get("max_items", 10)

        collected = []
        for s in sources:
            try:
                time.sleep(random.uniform(0.3, 1.0))  # 抖动，避免被源站限流
                text = self._fetch(s["url"])
                if not text:
                    continue
                for it in _parse_feed(text):
                    it["source"] = s["name"]
                    it["impact"] = self._classify(it.get("title", "") + " " + it.get("summary", ""))
                    collected.append(it)
            except Exception as e:
                logger.warning("Source %s failed: %s", s.get("name"), e)
                continue

        if not collected:
            return []

        # 去重（按 url）
        seen, uniq = set(), []
        for it in collected:
            key = it.get("url")
            if key in seen:
                continue
            seen.add(key)
            uniq.append(it)

        # 关键词命中优先，其余按出现顺序补足
        ranked = sorted(uniq, key=lambda x: _score(x), reverse=True)
        hit = [x for x in ranked if _score(x) > 0][:max_items]
        if len(hit) < max_items:
            hit += [x for x in ranked if _score(x) == 0][:max_items - len(hit)]
        return hit

    def _classify(self, text):
        pos = ["rise", "rally", "gain", "boost", "stimulus", "record", "涨", "利好", "反弹", "创新高", "回升"]
        neg = ["fall", "drop", "slump", "decline", "risk", "sanction", "tariff", "crash", "跌", "利空", "下挫", "暴跌", "制裁", "关税"]
        t = text.lower()
        p = sum(1 for k in pos if k in t)
        n = sum(1 for k in neg if k in t)
        return "利好" if p > n else ("利空" if n > p else "中性")
