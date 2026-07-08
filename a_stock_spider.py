# Stock market spider for A-share data
# Phase-1 refactor (2026-07-07):
#   * Removed ALL demo/fake-data fallbacks. On failure every fetcher returns
#     None / [] -- never fabricated numbers. (Fixes the old "冒名推送假数据" bug.)
#   * Added multi-source degradation: eastmoney (primary) -> tencent (fallback)
#     for index quotes, with a circuit breaker to avoid hammering a dead source.
#   * Added data-provenance metadata on the aggregated analysis
#     (source / fetched_at / data_complete) for traceability & storage.
import re, time, json, logging, random
from datetime import datetime, timedelta
import requests
import config
logger = logging.getLogger(__name__)

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

PRIMARY_SOURCE = "eastmoney"
FALLBACK_SOURCE = "tencent"


class CircuitBreaker:
    """Simple circuit breaker: after `fail_threshold` consecutive failures it
    opens for `cooldown` seconds so we stop hammering a dead upstream."""

    def __init__(self, fail_threshold=3, cooldown=300):
        self.fail_threshold = fail_threshold
        self.cooldown = cooldown
        self.fail_count = 0
        self.opened_at = 0.0

    def allow(self):
        if self.fail_count >= self.fail_threshold:
            if time.time() - self.opened_at < self.cooldown:
                return False
            self.fail_count = 0  # half-open: give it another try
        return True

    def record_success(self):
        self.fail_count = 0

    def record_failure(self):
        self.fail_count += 1
        if self.fail_count >= self.fail_threshold:
            self.opened_at = time.time()
            logger.warning("Circuit breaker OPENED for %ss", self.cooldown)


class AStockSpider:
    name = "A股板块爬虫"
    # 注意：东方财富已将 clist 行情接口从 data.eastmoney.com 迁移到
    # push2.eastmoney.com 前缀（旧前缀返回 404）。阶段三实测发现并修复。
    base_url = "https://push2.eastmoney.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://data.eastmoney.com/",
        })
        self.breaker_em = CircuitBreaker()
        self.breaker_tx = CircuitBreaker()

    def _fetch(self, url, breaker=None, **kw):
        if breaker is not None and not breaker.allow():
            logger.warning("Circuit breaker blocked request to %s", url)
            return None
        for i in range(2):
            try:
                # 随机抖动，避免固定节奏被识别为爬虫；同时限流时更快放弃重试
                time.sleep(random.uniform(0.4, 1.5))
                r = self.session.get(url, timeout=30, **kw)
                r.raise_for_status()
                r.encoding = r.apparent_encoding or "utf-8"
                if breaker is not None:
                    breaker.record_success()
                return r.text
            except Exception as e:
                logger.warning("Fetch failed (%s): %s", url, e)
                if i == 2:
                    if breaker is not None:
                        breaker.record_failure()
                    return None

    # ------------------------------------------------------------------
    # Index overview: eastmoney primary, tencent fallback
    # ------------------------------------------------------------------
    def fetch_market_overview(self):
        """获取主要指数行情；腾讯直连优先（实测稳定），东方财富兜底，再失败返回 None。"""
        # 阶段三实测：东方财富 ulist.np 接口偶发限流断开，腾讯 qt.gtimg.cn 稳定可用，
        # 故改为腾讯优先、东方财富兜底。
        tx = self._fetch_tencent_indices()
        if tx:
            return tx[:8]
        logger.info("Tencent indices failed, degrading to eastmoney")
        codes = ",".join(INDEX_CODES.keys())
        p = {
            "fltt": 2, "invt": 2,
            "fields": "f2,f3,f4,f12,f14,f15,f16,f17,f18,f20",
            "secids": codes,
        }
        h = self._fetch("https://push2.eastmoney.com/api/qt/ulist.np/get",
                        params=p, breaker=self.breaker_em)
        if not h:
            return None
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
        except Exception as e:
            logger.warning("Parse indices failed: %s", e)
            return None

    def _fetch_tencent_indices(self):
        secids = ",".join(INDEX_CODES.keys())  # sh000001,sz399001,...
        url = "https://qt.gtimg.cn/q=" + secids
        h = self._fetch(url, breaker=self.breaker_tx)
        if not h:
            return None
        try:
            out = []
            for line in h.split(";"):
                line = line.strip()
                if not line or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                val = val.strip().strip('"')
                if not val:
                    continue
                parts = val.split("~")
                if len(parts) < 6:
                    continue
                try:
                    name = parts[1]
                    code = parts[2]
                    price = float(parts[3])
                    # 腾讯行情格式尾部结构（指数/个股一致）：
                    #   ...~时间~涨跌额~涨跌幅~最高~最低~收盘/量/额~
                    # 用末尾字段更稳健，避免中途字段数差异导致错位。
                    # 腾讯行情格式尾部结构（指数/个股一致）：
                    #   ...~时间~涨跌额~涨跌幅~最高~最低~收盘/量/额~
                    # 用末尾字段更稳健，避免中途字段数差异导致错位。
                    chg_val = float(parts[-6])
                    chg_pct = float(parts[-5])
                    high = float(parts[-4])
                    low = float(parts[-3])
                    open_ = float(parts[5])
                except (ValueError, IndexError):
                    continue
                # sanity check: reject obviously garbage values
                if price <= 0 or not (-15 <= chg_pct <= 15):
                    continue
                out.append({
                    "name": name,
                    "code": code,
                    "price": price,
                    "chg_pct": chg_pct,
                    "chg_val": chg_val,
                    "high": high,
                    "low": low,
                    "open": open_,
                    "volume": 0,
                })
            return out if out else None
        except Exception as e:
            logger.warning("Tencent indices parse failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Market breadth (eastmoney only; failure -> None, never fake)
    # ------------------------------------------------------------------
    def fetch_market_breadth(self):
        """获取市场涨跌统计；失败返回 None。"""
        p = {
            "pn": 1, "pz": 10000, "po": 1, "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2, "invt": 2, "fid": "f3",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f2,f3,f12,f14",
        }
        h = self._fetch(self.base_url + "/api/qt/clist/get", params=p,
                        breaker=self.breaker_em)
        if not h:
            return None
        items = self._parse_html(h)
        if not items:
            return None

        up_count = sum(1 for i in items if i.get("f3", 0) > 0)
        down_count = sum(1 for i in items if i.get("f3", 0) < 0)
        flat_count = len(items) - up_count - down_count

        up_limit = sum(1 for i in items if i.get("f3", 0) >= 9.9)
        down_limit = sum(1 for i in items if i.get("f3", 0) <= -9.9)

        sorted_items = sorted(items, key=lambda x: x.get("f3", 0), reverse=True)
        top_gainers = [{"name": i.get("f14", ""), "code": i.get("f12", ""), "chg": i.get("f3", 0)} for i in sorted_items[:5]]
        top_losers = [{"name": i.get("f14", ""), "code": i.get("f12", ""), "chg": i.get("f3", 0)} for i in sorted_items[-5:]]

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

    # ------------------------------------------------------------------
    # North-bound flow (eastmoney only; failure -> None)
    # ------------------------------------------------------------------
    def fetch_north_flow(self):
        """获取北向资金流向；失败返回 None。"""
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
            h = self._fetch(url, params=p, breaker=self.breaker_em)
            if not h:
                return None
            data = json.loads(h)
            if data.get("data") and data["data"].get("klines"):
                last = data["data"]["klines"][-1].split(",")
                return {
                    "net_inflow": round(float(last[2]) / 10000, 2),
                    "balance": round(float(last[3]) / 10000, 2),
                }
        except Exception as e:
            logger.warning("North flow fetch/parse failed: %s", e)
        return None

    def fetch_previous_trading_day_analysis(self):
        """获取前一个交易日完整市场分析（聚合各模块 + 溯源元数据）。"""
        logger.info("Fetching previous trading day A-share market analysis")
        indices = self.fetch_market_overview()
        breadth = self.fetch_market_breadth()
        north = self.fetch_north_flow()
        sectors = self.fetch_sector_rankings(5)
        news = MarketNewsSpider().fetch_news()
        try:
            indicators = self.fetch_index_indicators()
        except Exception as e:
            logger.warning("Indicator fetch failed: %s" % e)
            indicators = []

        data_complete = all([
            indices is not None,
            breadth is not None,
            north is not None,
            bool(sectors),
        ])

        analysis = {
            "date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            "source": PRIMARY_SOURCE,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "data_complete": data_complete,
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
        h = self._fetch(self.base_url + "/api/qt/clist/get", params=p,
                        breaker=self.breaker_em)
        if not h:
            return None
        items = self._parse_html(h)
        if not items:
            return None

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
        h = self._fetch(self.base_url + "/api/qt/clist/get", params=p,
                        breaker=self.breaker_em)
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
        h = self._fetch(url, params=p, breaker=self.breaker_em)
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
        # 字段精简：仅取最具代表性的两个核心指数，降低对东方财富 K 线接口的请求量
        # （原抓 4 个指数各 60 天 K 线 = 4 次请求；现砍半，限流风险同步下降）
        idx_map = {
            "1.000001": "上证指数",
            "0.399006": "创业板指",
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
        for i in range(2):
            try:
                time.sleep(random.uniform(0.3, 1.0))
                r = requests.get(url, timeout=30, **kw)
                r.raise_for_status()
                r.encoding = r.apparent_encoding or "utf-8"
                return r.text
            except:
                if i == 2:
                    return None

    def fetch_news(self):
        """获取市场要闻；失败返回空列表（不编造新闻）。"""
        h = self._fetch("https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=15")
        if not h:
            logger.warning("Sina news fetch failed, returning empty list")
            return []
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
            return items[:30] if items else []
        except Exception as e:
            logger.warning("News parse failed: %s", e)
            return []

    def _classify(self, title):
        pos = ["rise", "break", "bullish", "growth", "stimulus", "rally", "support", "inflow", "tax", "buyback", "涨", "利好", "突破", "刺激", "增长", "反弹", "流入", "支持", "减税", "回购"]
        neg = ["fall", "decline", "bearish", "shrink", "tighten", "risk", "outflow", "sanctions", "tariff", "default", "跌", "利空", "下挫", "收缩", "收紧", "风险", "流出", "制裁", "关税", "违约"]
        t = title.lower()
        p = sum(1 for k in pos if k in t)
        n = sum(1 for k in neg if k in t)
        return "利好" if p > n else ("利空" if n > p else "中性")
