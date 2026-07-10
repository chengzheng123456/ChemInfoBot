import json
import unittest
from unittest import mock

import config
import neodata_news
from neodata_news import NeoDataNews


class TestNeoDataNews(unittest.TestCase):
    SAMPLE_JSON = json.dumps({
        "code": 200,
        "data": {
            "docData": {
                "docRecall": [
                    {"docList": [
                        {"title": "创指高开0.59%，CPO概念股大涨", "url": "http://gu.qq.com/x", "publishTime": "2026-07-10 09:44"},
                        {"title": "", "url": "http://gu.qq.com/y"},
                    ]}
                ]
            }
        }
    })

    def _patch_run(self, run_mock, stdout):
        run_mock.return_value = mock.Mock(stdout=stdout, stderr="")

    def test_parse_success(self):
        nd = NeoDataNews(token="tk_test", skill_dir="C:\\fake")
        with mock.patch.object(neodata_news.os.path, "isfile", return_value=True), \
             mock.patch.object(neodata_news.subprocess, "run") as run:
            self._patch_run(run, self.SAMPLE_JSON)
            items = nd.fetch_domestic_news()
        self.assertIsNotNone(items)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "创指高开0.59%，CPO概念股大涨")
        self.assertEqual(items[0]["source"], "国内·腾讯财经")
        self.assertEqual(items[0]["impact"], "国内要闻")
        self.assertEqual(items[0]["url"], "http://gu.qq.com/x")

    def test_token_empty_returns_none(self):
        with mock.patch.object(config, "NEODATA_TOKEN", ""):
            nd = NeoDataNews()
            with mock.patch.object(neodata_news.subprocess, "run") as run:
                items = nd.fetch_domestic_news()
        self.assertIsNone(items)
        run.assert_not_called()

    def test_script_missing_returns_none(self):
        nd = NeoDataNews(token="tk_test", skill_dir="C:\\not_exist_dir_xyz")
        items = nd.fetch_domestic_news()
        self.assertIsNone(items)

    def test_non_json_returns_none(self):
        nd = NeoDataNews(token="tk_test", skill_dir="C:\\fake")
        with mock.patch.object(neodata_news.os.path, "isfile", return_value=True), \
             mock.patch.object(neodata_news.subprocess, "run") as run:
            self._patch_run(run, "请求失败: HTTP 401")
            items = nd.fetch_domestic_news()
        self.assertIsNone(items)

    def test_code_not_200_returns_none(self):
        nd = NeoDataNews(token="tk_test", skill_dir="C:\\fake")
        bad = json.dumps({"code": 40101, "msg": "token invalid"})
        with mock.patch.object(neodata_news.os.path, "isfile", return_value=True), \
             mock.patch.object(neodata_news.subprocess, "run") as run:
            self._patch_run(run, bad)
            items = nd.fetch_domestic_news()
        self.assertIsNone(items)

    def test_subprocess_exception_returns_none(self):
        nd = NeoDataNews(token="tk_test", skill_dir="C:\\fake")
        with mock.patch.object(neodata_news.os.path, "isfile", return_value=True), \
             mock.patch.object(neodata_news.subprocess, "run", side_effect=Exception("boom")):
            items = nd.fetch_domestic_news()
        self.assertIsNone(items)


if __name__ == "__main__":
    unittest.main()
