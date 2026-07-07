# -*- coding: utf-8 -*-
"""精细探测：直接看各数据源接口的 HTTP 状态与返回内容，定位失效点。"""
import requests

SECIDS = "sh000001,sz399001,sz399006,sh000688,sh000300,sh000905,sh000852,sz399673"
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"}

URLS = {
    "指数(ulist/push2)": "https://push2.eastmoney.com/api/qt/ulist.np/get?"
        "fltt=2&invt=2&fields=f2,f3,f4,f12,f14,f15,f16,f17,f18,f20&secids=" + SECIDS,
    "涨跌(clist/data)": "https://data.eastmoney.com/api/qt/clist/get?"
        "pn=1&pz=10000&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&"
        "fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048&fields=f2,f3,f12,f14",
    "涨跌(clist/push2)": "https://push2.eastmoney.com/api/qt/clist/get?"
        "pn=1&pz=10000&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&"
        "fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048&fields=f2,f3,f12,f14",
    "板块(clist/push2,m:90)": "https://push2.eastmoney.com/api/qt/clist/get?"
        "pn=1&pz=8&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&"
        "fid=f3&fs=m:90+t:2&fields=f2,f3,f4,f12,f14",
    "腾讯(qt.gtimg)": "https://qt.gtimg.cn/q=" + SECIDS,
    "北向(kamt/push2)": "https://push2.eastmoney.com/api/qt/kamt.kline/get?"
        "fields1=f1,f2,f3,f4&fields2=f51,f52,f53,f54&klt=101&lmt=1&secid=90.001133&"
        "ut=7eea3edcaed734bea9cbfce24459ed5f",
}


def diag(name, url):
    print("\n>>> [%s]" % name)
    try:
        r = requests.get(url, headers=UA, timeout=15)
        print("    HTTP %s | len=%d" % (r.status_code, len(r.text)))
        preview = r.text.replace("\n", " ")[:240]
        print("    body: " + preview)
    except Exception as e:
        print("    EXCEPTION: %s" % e)


if __name__ == "__main__":
    for name, url in URLS.items():
        diag(name, url)
    print("\n=== 诊断结束 ===")
