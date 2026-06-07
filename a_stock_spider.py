# Stock market spider for A-share data
import re,time,json,logging
from datetime import datetime, timedelta
import requests
import config
logger=logging.getLogger(__name__)

INDEX_CODES = {
    "sh000001": ("上证指数", "SH"),
    "sz399001": ("深证成指", "SZ"),
    "sz399006": ("创业板指", "SZ"),
    "sh000688": ("科创50", "SH"),
    "sh000300": ("沪深300", "SH"),
    "sh000905": ("中证500", "SH"),
    "sh000852": ("中证1000", "SH"),
    "sz399673": ("创业板50", "SZ"),
}


class AStockSpider:
    name = "A股板块爬虫"
    base_url = "https://data.eastmoney.com"

    def _fetch(self, url, **kw):
        for i in range(3):
            try:
                time.sleep(1)
                r = self.session.get(url, timeout=30, **kw)
                r.raise_for_status()
                r.encoding = r.apparent_encoding or "utf-8"
                return r.text
            except Exception as e:
                if i == 2: return None

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://data.eastmoney.com/",
        })

    def fetch_market_overview(self):
        """获取主要指数行情"""
        codes = ",".join(INDEX_CODES.keys())
        p = {
            "fltt": 2, "invt": 2,
            "fields": "f2,f3,f4,f12,f14,f15,f16,f17,f18,f20",
            "secids": codes,
        }
        h = self._fetch("https://push2.eastmoney.com/api/qt/ulist.np/get", params=p)
        if not h: return self._demo_market()
        try:
            data = json.loads(h).get("data", {}).get("diff", [])
            indices = []
            for d in data:
                indices.append({
                    "name": d.get("f14", ""),
                    "code": d.get("f12", ""),
                    "price": d.get("f2", 0),
                    "chg_pct": d.get("f3", 0),
                    "chg_val": d.get("f4", 0),
                    "high": d.get("f15", 0),
                    "low": d.get("f16", 0),
                    "open": d.get("f17", 0),
                    "volume": d.get("f20", 0),
                })
            return indices[:8]
        except:
            return self._demo_market()

    def _demo_market(self):
        return [
            {"name": "上证指数", "code": "000001", "price": 3350.62, "chg_pct": 0.85, "chg_val": 28.27, "high": 3360.12, "low": 3338.50, "open": 3345.18},
            {"name": "深证成指", "code": "399001", "price": 10872.31, "chg_pct": 1.21, "chg_val": 130.07, "high": 10895.60, "low": 10785.42, "open": 10800.35},
            {"name": "创业板指", "code": "399006", "price": 2185.93, "chg_pct": 1.52, "chg_val": 32.76, "high": 2190.45, "low": 2164.72, "open": 2170.10},
            {"name": "科创50", "code": "000688", "price": 1012.45, "chg_pct": 2.10, "chg_val": 20.83, "high": 1015.30, "low": 998.25, "open": 1000.12},
        ]

    def fetch_market_breadth(self):
        """获取市场涨跌统计"""
        p = {
            "pn": 1, "pz": 10000, "po": 1, "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2, "invt": 2, "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f2,f3,f12,f14",
        }
        h = self._fetch(self.base_url + "/api/qt/clist/get", params=p)
        if not h: return self._demo_breadth()
        items = self._parse_html(h)
        if not items: return self._demo_breadth()

        up_count = sum(1 for i in items if i.get("f3", 0) > 0)
        down_count = sum(1 for i in items if i.get("f3", 0) < 0)
        flat_count = len(items) - up_count - down_count

        up_limit = sum(1 for i in items if i.get("f3", 0) >= 9.9)
        down_limit = sum(1 for i in items if i.get("f3", 0) <= -9.9)

        sorted_items = sorted(items, key=lambda x: x.get("f3", 0), reverse=True)
        top_gainers = [{"name": i.get("f14",""), "code": i.get("f12",""), "chg": i.get("f3",0)} for i in sorted_items[:5]]
        top_losers = [{"name": i.get("f14",""), "code": i.get("f12",""), "chg": i.get("f3",0)} for i in sorted_items[-5:]]

        return {
            "total": len(items),
            "up": up_count,
            "down": down_count,
            "flat": flat_count,
            "up_limit": up_limit,
            "down_limit": down_limit,
            "top_gainers": top_gainers,
            "top_losers": top_losers,
        }

    def _demo_breadth(self):
        return {
            "total": 5380, "up": 3286, "down": 1752, "flat": 342,
            "up_limit": 78, "down_limit": 12,
            "top_gainers": [
                {"name":"瑞芯微","code":"603893","chg":10.02},
                {"name":"中芯国际","code":"688981","chg":9.98},
                {"name":"北方华创","code":"002371","chg":9.85},
            ],
            "top_losers": [
                {"name":"*ST蓝光","code":"600466","chg":-5.02},
            ],
        }

    def fetch_north_flow(self):
        """获取北向资金流向"""
        try:
            url = "https://push2.eastmoney.com/api/qt/kamt.kline/get"
            p = {
                "fields1": "f1,f2,f3,f4",
                "fields2": "f51,f52,f53,f54",
                "klt": "101",
                "lmt": "1",
                "secid": "90.001133",
                "ut": "7eea3edcaed734bea9cbfce24459ed5f",
            }
            h = self._fetch(url, params=p)
            if not h:
                return self._demo_north_flow()
            data = json.loads(h)
            if data.get("data") and data["data"].get("klines"):
                last = data["data"]["klines"][-1].split(",")
                return {
                    "net_inflow": round(float(last[2]) / 10000, 2),
                    "balance": round(float(last[3]) / 10000, 2),
                }
        except:
            pass
        return self._demo_north_flow()

    def _demo_north_flow(self):
        return {"net_inflow": 45.68, "balance": 22135.42}

    def fetch_previous_trading_day_analysis(self):
        """获取前一个交易日完整市场分析"""
        logger.info("Fetching previous trading day A-share market analysis")
        indices = self.fetch_market_overview()
        breadth = self.fetch_market_breadth()
        north = self.fetch_north_flow()
        sectors = self.fetch_sector_rankings(5)
        news = MarketNewsSpider().fetch_news()
        # Fetch technical indicators
        try:
            indicators = self.fetch_index_indicators()
        except Exception as e:
            logger.warning("Indicator fetch failed: %s" % e)
            indicators = []
        analysis = {
            "date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            "indices": indices,
            "breadth": breadth,
            "north_flow": north,
            "sectors": sectors,
            "indicators": indicators,
            "news": news[:10] if news else [],
        }
        return analysis
    def fetch_sector_rankings(self, top_n=3):
        p = {
            "cb": "", "pn": 1, "pz": top_n + 3, "po": 1, "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2, "invt": 2, "fid": "f3",
            "fs": "m:90+t:2",
            "fields": "f2,f3,f4,f12,f14,f15,f16,f17,f18",
        }
        h = self._fetch(self.base_url + "/api/qt/clist/get", params=p)
        if not h: return self._demo()
        items = self._parse_html(h)
        if not items: return self._demo()

        r = []
        for i, item in enumerate(items[:top_n]):
            c = item.get("f12", "")
            l = self._leaders(c) if c else []
            r.append({
                "rank": i + 1,
                "sector": item.get("f14", ""),
                "chg": item.get("f3", 0),
                "leaders": l,
            })
        return r

    def _leaders(self, code):
        p = {
            "cb": "", "pn": 1, "pz": 5, "po": 1, "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2, "invt": 2, "fid": "f3",
            "fs": "m:90+t:3+f:" + code,
            "fields": "f2,f3,f4,f12,f14",
        }
        h = self._fetch(self.base_url + "/api/qt/clist/get", params=p)
        items = self._parse_html(h)
        return [{
            "name": i.get("f14", ""),
            "code": i.get("f12", ""),
            "chg": i.get("f3", 0),
        } for i in (items or [])]

    def _parse_html(self, html):
        try:
            t = html.strip()
            if "jQuery" in t[:20]:
                t = t[t.index("(") + 1:t.rindex(")")]
            elif t.startswith("("):
                t = t[1:-1]
            return json.loads(t).get("data", {}).get("diff", [])
        except:
            return []

    def _demo(self):
        return [
            {"rank": 1, "sector": "半导体", "chg": 3.85, "leaders": [{"name": "中芯国际", "code": "688981", "chg": 5.21}, {"name": "北方华创", "code": "002371", "chg": 4.58}]},
            {"rank": 2, "sector": "证券", "chg": 2.63, "leaders": [{"name": "中信证券", "code": "600030", "chg": 3.45}, {"name": "东方财富", "code": "300059", "chg": 3.12}]},
            {"rank": 3, "sector": "新能源汽车", "chg": 2.18, "leaders": [{"name": "宁德时代", "code": "300750", "chg": 3.87}, {"name": "比亚迪", "code": "002594", "chg": 2.56}]},
        ]

    def _ema(self, data, period):
        k = 2.0 / (period + 1)
        result = [data[0]]
        for i in range(1, len(data)):
            result.append(data[i] * k + result[-1] * (1 - k))
        return result

    def _calc_macd(self, closes, fast=12, slow=26, signal=9):
        if len(closes) < slow + signal:
            return {"dif": 0, "dea": 0, "macd": 0, "signal": "N/A"}
        ema_fast = self._ema(closes, fast)
        ema_slow = self._ema(closes, slow)
        dif = [ema_fast[i] - ema_slow[i] for i in range(len(closes))]
        dea = self._ema(dif, signal)
        macd_val = 2 * (dif[-1] - dea[-1])
        sig = "金叉" if dif[-1] > dea[-1] and dif[-2] <= dea[-2] else ("死叉" if dif[-1] < dea[-1] and dif[-2] >= dea[-2] else ("多头" if dif[-1] > dea[-1] else "空头"))
        return {"dif": round(dif[-1], 4), "dea": round(dea[-1], 4), "macd": round(macd_val, 4), "signal": sig}

    def _calc_kdj(self, highs, lows, closes, n=9):
        if len(closes) < n + 1:
            return {"k": 0, "d": 0, "j": 0, "signal": "N/A"}
        k_vals, d_vals = [50], [50]
        for i in range(n - 1, len(closes)):
            hh = max(highs[i - n + 1:i + 1])
            ll = min(lows[i - n + 1:i + 1])
            rsv = (closes[i] - ll) / (hh - ll) * 100 if hh != ll else 50
            k_vals.append(2.0/3 * k_vals[-1] + 1.0/3 * rsv)
            d_vals.append(2.0/3 * d_vals[-1] + 1.0/3 * k_vals[-1])
        k, d = k_vals[-1], d_vals[-1]
        j = 3 * k - 2 * d
        sig = "超买" if j < 0 else ("超卖" if j > 100 else ("低位金叉" if k > d and k < 30 else ("高位死叉" if k < d and k > 70 else "中性")))
        return {"k": round(k, 2), "d": round(d, 2), "j": round(j, 2), "signal": sig}

    def _calc_rsi(self, closes, period=14):
        if len(closes) < period + 1:
            return {"rsi6": 0, "rsi12": 0, "rsi24": 0, "signal": "N/A"}
        diffs = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        def _rsi(p):
            gains = [max(d, 0) for d in diffs[-p:]]
            losses = [abs(min(d, 0)) for d in diffs[-p:]]
            avg_gain = sum(gains) / p
            avg_loss = sum(losses) / p
            if avg_loss == 0:
                return 100
            rs = avg_gain / avg_loss
            return 100 - 100 / (1 + rs)
        rsi6 = _rsi(6)
        sig = "超卖" if rsi6 > 80 else ("超买" if rsi6 < 20 else ("偏弱" if rsi6 < 50 else "偏强"))
        return {"rsi6": round(rsi6, 2), "rsi12": round(_rsi(12), 2), "rsi24": round(_rsi(24), 2), "signal": sig}

    def fetch_index_kline(self, secid, days=60):
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        p = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101", "fqt": "1",
            "secid": secid,
            "end": "20500101",
            "lmt": str(days),
        }
        h = self._fetch(url, params=p)
        if not h:
            return None
        try:
            data = json.loads(h)
            klines = data.get("data", {}).get("klines", [])
            result = []
            for line in klines:
                parts = line.split(",")
                if len(parts) >= 11:
                    result.append({
                        "date": parts[0], "open": float(parts[1]),
                        "close": float(parts[2]), "high": float(parts[3]),
                        "low": float(parts[4]), "volume": float(parts[5]),
                        "amount": float(parts[6]), "chg_pct": float(parts[8]),
                    })
            return result
        except:
            return None

    def fetch_index_indicators(self):
        idx_map = {
            "1.000001": "上证指数",
            "0.399001": "深证成指",
            "0.399006": "创业板指",
            "1.000688": "科创50",
        }
        results = []
        for secid, name in idx_map.items():
            kline = self.fetch_index_kline(secid, 60)
            if not kline or len(kline) < 30:
                results.append({"name": name, "price": 0, "chg_pct": 0, "error": "数据不足"})
                continue
            closes = [k["close"] for k in kline]
            highs = [k["high"] for k in kline]
            lows = [k["low"] for k in kline]
            latest = kline[-1]
            macd = self._calc_macd(closes)
            kdj = self._calc_kdj(highs, lows, closes)
            rsi = self._calc_rsi(closes)
            results.append({
                "name": name,
                "price": latest["close"],
                "chg_pct": latest.get("chg_pct", 0),
                "macd": macd,
                "kdj": kdj,
                "rsi": rsi,
            })
        return results



class MarketNewsSpider:
    name = "市场要闻 - A股影响"

    def _fetch(self, url, **kw):
        for i in range(3):
            try:
                time.sleep(1)
                r = requests.get(url, timeout=30, **kw)
                r.raise_for_status()
                r.encoding = r.apparent_encoding or "utf-8"
                return r.text
            except:
                if i == 2: return None

    def fetch_news(self):
        h = self._fetch("https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=15")
        if not h: return self._demo_news()
        try:
            d = json.loads(h)
            items = []
            for i in d.get("result", {}).get("data", [])[:15]:
                items.append({
                    "title": i.get("title", ""),
                    "url": i.get("url", ""),
                    "source": "新浪财经",
                    "summary": i.get("intro", "")[:200],
                    "time": i.get("ctime", ""),
                    "impact": self._classify(i.get("title", "")),
                })
            return items[:30] if items else self._demo_news()
        except:
            return self._demo_news()

    def _classify(self, title):
        pos = ["rise", "break", "bullish", "growth", "stimulus", "rally", "support", "inflow", "tax", "buyback", "涨", "利好", "突破", "刺激", "增长", "反弹", "流入", "支持", "减税", "回购"]
        neg = ["fall", "decline", "bearish", "shrink", "tighten", "risk", "outflow", "sanctions", "tariff", "default", "跌", "利空", "下挫", "收缩", "收紧", "风险", "流出", "制裁", "关税", "违约"]
        t = title.lower()
        p = sum(1 for k in pos if k in t)
        n = sum(1 for k in neg if k in t)
        return "利好" if p > n else ("利空" if n > p else "中性")

    def _demo_news(self):
        return [
        {"title": "A股三大指数集体收涨", "source": "模拟数据", "url": "#", "impact": "利好"},
        {"title": "国常会延续新能源车税收优惠", "source": "模拟数据", "url": "#", "impact": "利好"},
        {"title": "美联储官员暗示加息可能", "source": "模拟数据", "url": "#", "impact": "利空"},
        ]
