"""
国内 A 股要闻加成层（可选）。

复用本机 WorkBuddy 内置 neodata-financial-search 技能的 query.py，
取 docRecall（国内财经新闻 / 公司公告 / 政策解读），并入 bot「市场要闻」。

降级策略（任何失败都静默跳过，主报告不受影响）：
  - config.NEODATA_TOKEN 为空        -> 返回 None（零开销，不调用）
  - 脚本路径不存在                   -> 返回 None
  - 调用异常 / 超时 / 非 JSON 输出   -> 返回 None（如 token 过期，stdout 为空）
  - 返回 code != 200 / 无 docData    -> 返回 None
"""
import json
import os
import sys
import subprocess
import logging

import config

logger = logging.getLogger(__name__)

DEFAULT_SKILL_DIR = r"D:\Program Files\WorkBuddy\resources\app.asar.unpacked\resources\builtin-skills\neodata-financial-search\scripts"

QUERY = "今日A股市场重要新闻、公司公告、政策解读与行业动态"


class NeoDataNews:
    def __init__(self, skill_dir=None, token=None):
        self.skill_dir = skill_dir or getattr(config, "NEODATA_SKILL_DIR", DEFAULT_SKILL_DIR)
        self.token = token if token is not None else getattr(config, "NEODATA_TOKEN", "")

    def fetch_domestic_news(self, limit=8):
        """返回国内 A 股要闻列表 [{title,url,source,impact,time}] 或 None（降级）。"""
        if not self.token:
            logger.info("[neodata] token 未配置，跳过国内要闻加成层。")
            return None
        query_script = os.path.join(self.skill_dir, "query.py")
        if not os.path.isfile(query_script):
            logger.warning("[neodata] query.py 不存在: %s，跳过。", query_script)
            return None

        try:
            proc = subprocess.run(
                [sys.executable, query_script,
                 "--query", QUERY, "--data-type", "doc", "--token", self.token],
                capture_output=True, text=True, timeout=60,
            )
        except Exception as e:
            logger.warning("[neodata] 调用失败: %s", e)
            return None

        if proc.stderr.strip():
            logger.debug("[neodata] stderr: %s", proc.stderr.strip()[:200])

        try:
            data = json.loads(proc.stdout)
        except Exception:
            logger.warning("[neodata] 返回非 JSON（可能 token 过期），降级跳过。")
            return None

        if data.get("code") not in (200, "200"):
            logger.warning("[neodata] 返回 code=%s，降级跳过。", data.get("code"))
            return None

        doc_recall = (data.get("data") or {}).get("docData", {}).get("docRecall", [])
        items = []
        for grp in doc_recall:
            for doc in grp.get("docList", []):
                title = (doc.get("title") or "").strip()
                if not title:
                    continue
                items.append({
                    "title": title,
                    "url": doc.get("url") or "#",
                    "source": "国内·腾讯财经",
                    "impact": "国内要闻",
                    "time": str(doc.get("publishTime", "")),
                })
        if not items:
            logger.info("[neodata] 未召回文档，降级跳过。")
            return None
        logger.info("[neodata] 取到国内要闻 %d 条。", len(items))
        return items[:limit]
