# 国际财经 RSS 模块测试（mock 网络，不真实抓取）
import unittest
from unittest.mock import patch
from world_news_spider import WorldNewsSpider, _parse_feed

RSS_XML = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>China stocks rally on stimulus</title><link>https://bbc.com/1</link><description>Shanghai composite up 2%</description><pubDate>Wed, 08 Jul 2026 01:00:00 GMT</pubDate></item>
<item><title>Local cat wins national award</title><link>https://bbc.com/2</link><description>cute and fluffy</description><pubDate>Wed, 08 Jul 2026 02:00:00 GMT</pubDate></item>
</channel></rss>"""

ATOM_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<title>Federal Reserve holds interest rates steady</title><link href="https://ap.com/1"/><summary>Fed pauses amid inflation data</summary><updated>2026-07-08T03:00:00Z</updated>
</entry></feed>"""


class TestParse(unittest.TestCase):
    def test_parse_rss(self):
        items = _parse_feed(RSS_XML)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "China stocks rally on stimulus")
        self.assertEqual(items[0]["url"], "https://bbc.com/1")
        self.assertIn("Shanghai", items[0]["summary"])

    def test_parse_atom(self):
        items = _parse_feed(ATOM_XML)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], "https://ap.com/1")
        self.assertIn("Federal Reserve", items[0]["title"])

    def test_parse_empty(self):
        self.assertEqual(_parse_feed(""), [])
        self.assertEqual(_parse_feed("<notxml"), [])


class TestFetch(unittest.TestCase):
    def test_keyword_ranking(self):
        spider = WorldNewsSpider()
        # 5 个默认源，依次返回 RSS / 空 / ATOM / 空 / 空
        with patch.object(WorldNewsSpider, "_fetch", side_effect=[RSS_XML, "", ATOM_XML, "", ""]):
            res = spider.fetch_news(max_items=10)
        titles = [r["title"] for r in res]
        # 命中关键词的国际面条目应被收录
        self.assertIn("China stocks rally on stimulus", titles)
        self.assertIn("Federal Reserve holds interest rates steady", titles)
        # 未命中（cat）的应被排在后面或被截断，不挤掉命中项
        self.assertNotIn("Local cat wins national award", titles[:2])

    def test_fallback_when_all_fail(self):
        spider = WorldNewsSpider()
        with patch.object(WorldNewsSpider, "_fetch", return_value=None):
            res = spider.fetch_news()
        self.assertEqual(res, [])

    def test_no_duplicate(self):
        spider = WorldNewsSpider()
        with patch.object(WorldNewsSpider, "_fetch", return_value=RSS_XML):
            res = spider.fetch_news()
        urls = [r["url"] for r in res]
        self.assertEqual(len(urls), len(set(urls)))

    def test_disabled(self):
        spider = WorldNewsSpider()
        with patch.object(WorldNewsSpider, "_fetch", return_value=RSS_XML):
            res = spider.fetch_news()
        # 验证结构完整（含 source / impact 字段）
        self.assertTrue(all("source" in r and "impact" in r for r in res))


if __name__ == "__main__":
    unittest.main()
