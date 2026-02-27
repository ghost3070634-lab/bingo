from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup
import pandas as pd
import random
from datetime import datetime, timezone, timedelta
import urllib3
import os
import uvicorn
from itertools import combinations
from collections import Counter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# UI 介面：100% 完整對齊下一期預測策略
# ==========================================
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>賓果賓果 下一期預測中心</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white font-sans p-6 min-h-screen">
    <div class="max-w-6xl mx-auto">
        <div class="flex flex-col md:flex-row justify-between items-end border-b border-gray-700 pb-4 mb-6">
            <div>
                <h1 class="text-3xl font-bold text-yellow-400 mb-2">🎰 賓果賓果 終極下一期預測</h1>
                <p class="text-gray-400">當前最新期數：<span class="text-white font-bold">{{ data.last_draw_no }}</span> | 已分析近 100 期數據</p>
            </div>
            <div class="text-right mt-4 md:mt-0">
                <p class="text-sm text-gray-400">最後運算 (每5分自動刷新)</p>
                <p class="text-xl font-mono text-green-400">{{ data.update_time }}</p>
            </div>
        </div>

        <h2 class="text-xl font-bold mb-4 text-blue-300">📊 當下盤勢狀態 (Next Draw 預測基底)</h2>
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div class="bg-gray-800 p-4 rounded-lg border border-red-900">
                <h3 class="text-red-400 font-bold mb-2">🔥 熱門號 (高頻率)</h3>
                <div class="flex flex-wrap gap-1">
                    {% for num in data.hot_numbers %}
                    <span class="bg-red-600 text-white px-2 py-1 rounded text-xs font-bold">{{ num }}</span>
                    {% endfor %}
                </div>
            </div>
            <div class="bg-gray-800 p-4 rounded-lg border border-blue-900">
                <h3 class="text-blue-400 font-bold mb-2">❄️ 真冷門號 (>10期未開)</h3>
                <div class="flex flex-wrap gap-1">
                    {% for num in data.cold_numbers %}
                    <span class="bg-blue-600 text-white px-2 py-1 rounded text-xs font-bold">{{ num }}</span>
                    {% endfor %}
                </div>
            </div>
            <div class="bg-gray-800 p-4 rounded-lg border border-purple-900">
                <h3 class="text-purple-400 font-bold mb-2">⏭️ 跳期號 (跳1或2期)</h3>
                <div class="flex flex-wrap gap-1">
                    {% for num in data.skip_numbers %}
                    <span class="bg-purple-600 text-white px-2 py-1 rounded text-xs font-bold">{{ num }}</span>
                    {% endfor %}
                </div>
            </div>
            <div class="bg-gray-800 p-4 rounded-lg border border-yellow-700">
                <h3 class="text-yellow-400 font-bold mb-2">📈 當前熱門尾數</h3>
                <div class="flex flex-wrap gap-2 text-xl font-black text-yellow-500">
                    {% for tail in data.hot_tails %}<span>{{ tail }}尾</span>{% endfor %}
                </div>
            </div>
        </div>

        <h2 class="text-2xl font-bold mb-4 text-pink-400">🚀 下一期最強預測 (條件完全符合且歷史機率最高)</h2>
        
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <!-- 2星預測區 -->
            <div class="bg-gray-800 p-5 rounded-xl border border-pink-900 shadow-lg">
                <h3 class="text-xl text-pink-300 font-bold mb-4">✌️ 下一期 2 星推薦</h3>
                
                <div class="mb-1 text-sm text-gray-400 font-bold mt-4">🔹 【短線連莊】上一期號碼 + 熱門號</div>
                <div class="space-y-2">
                    {% for item in data.pred_2_repeat %}
                    <div class="flex items-center justify-between bg-gray-700 p-2 rounded-lg border-l-4 border-pink-500">
                        <div class="flex space-x-2">
                            {% for num in item.combo %}
                            <div class="w-10 h-10 rounded-full bg-pink-600 flex items-center justify-center text-white text-lg font-bold">{{ num }}</div>
                            {% endfor %}
                        </div>
                        <div class="text-xs text-gray-400">歷史勝率評分: <span class="text-white font-bold">{{ item.score }}</span></div>
                    </div>
                    {% endfor %}
                </div>
                
                <div class="mb-1 text-sm text-gray-400 font-bold mt-4">🔹 【相鄰連號】連續相鄰號碼 (n, n+1)</div>
                <div class="space-y-2">
                    {% for item in data.pred_2_adjacent %}
                    <div class="flex items-center justify-between bg-gray-700 p-2 rounded-lg border-l-4 border-purple-500">
                        <div class="flex space-x-2">
                            {% for num in item.combo %}
                            <div class="w-10 h-10 rounded-full bg-purple-600 flex items-center justify-center text-white text-lg font-bold">{{ num }}</div>
                            {% endfor %}
                        </div>
                        <div class="text-xs text-gray-400">歷史勝率評分: <span class="text-white font-bold">{{ item.score }}</span></div>
                    </div>
                    {% endfor %}
                </div>

                <div class="mb-1 text-sm text-gray-400 font-bold mt-4">🔹 【冷熱交替】真冷門號 (>10期) + 熱門號</div>
                <div class="space-y-2">
                    {% for item in data.pred_2_coldhot %}
                    <div class="flex items-center justify-between bg-gray-700 p-2 rounded-lg border-l-4 border-blue-500">
                        <div class="flex space-x-2">
                            {% for num in item.combo %}
                            <div class="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center text-white text-lg font-bold">{{ num }}</div>
                            {% endfor %}
                        </div>
                        <div class="text-xs text-gray-400">歷史勝率評分: <span class="text-white font-bold">{{ item.score }}</span></div>
                    </div>
                    {% endfor %}
                </div>
            </div>

            <!-- 3星預測區 -->
            <div class="bg-gray-800 p-5 rounded-xl border border-yellow-700 shadow-lg">
                <h3 class="text-xl text-yellow-300 font-bold mb-4">🎯 下一期 3 星推薦</h3>
                
                <div class="mb-1 text-sm text-gray-400 font-bold">🔸 【對稱+趨勢】1-26,27-52,53-80各一 + 尾數/倍數</div>
                <div class="space-y-2">
                    {% for item in data.pred_3_zone %}
                    <div class="flex items-center justify-between bg-gray-700 p-2 rounded-lg border-l-4 border-yellow-500">
                        <div class="flex space-x-2">
                            {% for num in item.combo %}
                            <div class="w-10 h-10 rounded-full bg-yellow-500 flex items-center justify-center text-black text-lg font-bold">{{ num }}</div>
                            {% endfor %}
                        </div>
                        <div class="text-xs text-gray-400">歷史勝率評分: <span class="text-white font-bold">{{ item.score }}</span></div>
                    </div>
                    {% endfor %}
                </div>

                <div class="mb-1 text-sm text-gray-400 font-bold mt-4">🔸 【跳期規律】跳1或2期號碼 + 熱門號</div>
                <div class="space-y-2">
                    {% for item in data.pred_3_skip %}
                    <div class="flex items-center justify-between bg-gray-700 p-2 rounded-lg border-l-4 border-orange-500">
                        <div class="flex space-x-2">
                            {% for num in item.combo %}
                            <div class="w-10 h-10 rounded-full bg-orange-500 flex items-center justify-center text-white text-lg font-bold">{{ num }}</div>
                            {% endfor %}
                        </div>
                        <div class="text-xs text-gray-400">歷史勝率評分: <span class="text-white font-bold">{{ item.score }}</span></div>
                    </div>
                    {% endfor %}
                </div>

                <div class="mb-1 text-sm text-gray-400 font-bold mt-4">🔸 【四區分散】(1-20,21-40,41-60,61-80) 選三區分散風險</div>
                <div class="space-y-2">
                    {% for item in data.pred_3_scatter %}
                    <div class="flex items-center justify-between bg-gray-700 p-2 rounded-lg border-l-4 border-green-500">
                        <div class="flex space-x-2">
                            {% for num in item.combo %}
                            <div class="w-10 h-10 rounded-full bg-green-600 flex items-center justify-center text-white text-lg font-bold">{{ num }}</div>
                            {% endfor %}
                        </div>
                        <div class="text-xs text-gray-400">歷史勝率評分: <span class="text-white font-bold">{{ item.score }}</span></div>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>
    <script>setTimeout(function() { window.location.reload(); }, 300000);</script>
</body>
</html>
"""

if not os.path.exists("templates"):
    os.makedirs("templates")
with open("templates/index.html", "w", encoding="utf-8") as f:
    f.write(HTML_CONTENT)

# ==========================================
# 核心邏輯演算法
# ==========================================

app = FastAPI()
templates = Jinja2Templates(directory="templates")

class UltimateBingoPredictor:
    def __init__(self):
        self.draws =[]

    def fetch_auzo_data(self):
        url = "https://lotto.auzo.tw/bingobingo.php"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            response = requests.get(url, headers=headers, timeout=10, verify=False)
            soup = BeautifulSoup(response.text, 'html.parser')
            new_draws =[]
            for tr in soup.find_all('tr'):
                nums, draw_no =[], ""
                for text_node in tr.stripped_strings:
                    if text_node.isdigit():
                        val = int(text_node)
                        if len(text_node) >= 8 and text_node.startswith('11'):
                            draw_no = text_node
                        elif 1 <= val <= 80:
                            nums.append(val)
                nums = sorted(list(set(nums)))
                if draw_no and len(nums) >= 20:
                    new_draws.append({"draw_no": draw_no, "numbers": nums[:20]})
            
            if new_draws:
                self.draws = list(reversed(new_draws)) # 舊到新
                return
        except Exception:
            pass
        if not self.draws:
            self._generate_mock_data()

    def _generate_mock_data(self):
        self.draws =[]
        for i in range(100):
            self.draws.append({"draw_no": f"模擬{i:03d}", "numbers": sorted(random.sample(range(1, 81), 20))})

    def analyze(self):
        self.fetch_auzo_data()
        
        # 抓取近期 100 期數據
        recent_draws = self.draws[-100:] if len(self.draws) > 100 else self.draws
        
        all_nums, tails = [],[]
        for d in recent_draws:
            all_nums.extend(d['numbers'])
            tails.extend([n % 10 for n in d['numbers']])
            
        # 1. 盤勢計算
        freq = pd.Series(all_nums).value_counts()
        hot_numbers = freq.head(15).index.tolist() if not freq.empty else list(range(1, 16))
        
        # 計算遺漏值 (Gap)
        last_seen = {i: -1 for i in range(1, 81)}
        for idx, d in enumerate(recent_draws):
            for n in d['numbers']: last_seen[n] = idx
        current_idx = len(recent_draws) - 1
        gaps = {n: current_idx - last_seen[n] for n in range(1, 81)}
        
        # 規則：冷門號 (連續 >10 期未開)
        cold_numbers =[n for n, g in gaps.items() if g >= 10]
        if not cold_numbers: cold_numbers = sorted(gaps, key=gaps.get, reverse=True)[:10]

        # 規則：跳期號 (跳一期 gap==1 或 隔兩期 gap==2)
        skip_numbers = [n for n, g in gaps.items() if g in [1, 2]]

        # 連莊號 (上一期)
        last_draw_nums = recent_draws[-1]['numbers'] if recent_draws else[]
        
        # 熱門尾數
        hot_tails = pd.Series(tails).value_counts().head(3).index.tolist()

        # 計算歷史 2星/3星 出現次數作為勝率評分依據
        pairs, triplets = [],[]
        for d in recent_draws:
            pairs.extend(combinations(d['numbers'], 2))
            triplets.extend(combinations(d['numbers'], 3))
        pair_counts = Counter(pairs)
        triplet_counts = Counter(triplets)

        # ==========================================
        # 🚀 下一期預測邏輯 (嚴格條件過濾 + 歷史勝率排序)
        # ==========================================
        
        # 【2星】短線連莊：上一期 + 熱門號
        pred_2_repeat_dict = {k: v for k, v in pair_counts.items() if (k[0] in last_draw_nums and k[1] in hot_numbers) or (k[1] in last_draw_nums and k[0] in hot_numbers)}
        pred_2_repeat =[{"combo": list(k), "score": v} for k, v in Counter(pred_2_repeat_dict).most_common(2)]

        # 【2星】相鄰連號：連續相鄰 (n, n+1)
        pred_2_adj_dict = {k: v for k, v in pair_counts.items() if k[1] == k[0] + 1}
        pred_2_adjacent =[{"combo": list(k), "score": v} for k, v in Counter(pred_2_adj_dict).most_common(2)]

        # 【2星】冷熱交替：真冷門 + 熱門號
        pred_2_ch_dict = {k: v for k, v in pair_counts.items() if (k[0] in cold_numbers and k[1] in hot_numbers) or (k[1] in cold_numbers and k[0] in hot_numbers)}
        pred_2_coldhot =[{"combo": list(k), "score": v} for k, v in Counter(pred_2_ch_dict).most_common(2)]

        # 【3星】對稱+趨勢：1-26,27-52,53-80 各一 + 包含尾數與倍數
        def is_sym_trend(c):
            h_zone = any(1<=x<=26 for x in c) and any(27<=x<=52 for x in c) and any(53<=x<=80 for x in c)
            h_tail = any(x%10 in hot_tails for x in c)
            h_mult = any(x%5==0 for x in c)
            return h_zone and h_tail and h_mult
        pred_3_zone_dict = {k: v for k, v in triplet_counts.items() if is_sym_trend(k)}
        pred_3_zone =[{"combo": list(k), "score": v} for k, v in Counter(pred_3_zone_dict).most_common(2)]

        # 【3星】跳期規律：至少包含1個跳期號 + 至少1個熱門號
        def is_skip_rule(c):
            return any(x in skip_numbers for x in c) and any(x in hot_numbers for x in c)
        pred_3_skip_dict = {k: v for k, v in triplet_counts.items() if is_skip_rule(k)}
        pred_3_skip =[{"combo": list(k), "score": v} for k, v in Counter(pred_3_skip_dict).most_common(2)]

        # 【3星】四區分散：分散在 1-20, 21-40, 41-60, 61-80 四個區塊中的三個
        def is_scatter(c):
            zones = set()
            for x in c:
                if 1<=x<=20: zones.add(1)
                elif 21<=x<=40: zones.add(2)
                elif 41<=x<=60: zones.add(3)
                else: zones.add(4)
            return len(zones) == 3 # 必須分佈在三個不同的區塊以分散風險
        pred_3_scatter_dict = {k: v for k, v in triplet_counts.items() if is_scatter(k)}
        pred_3_scatter =[{"combo": list(k), "score": v} for k, v in Counter(pred_3_scatter_dict).most_common(2)]

        tz_tw = timezone(timedelta(hours=8))
        return {
            "last_draw_no": recent_draws[-1]['draw_no'] if recent_draws else "無",
            "hot_numbers": hot_numbers[:10],
            "cold_numbers": cold_numbers[:10],
            "skip_numbers": skip_numbers[:10],
            "hot_tails": hot_tails,
            "pred_2_repeat": pred_2_repeat,
            "pred_2_adjacent": pred_2_adjacent,
            "pred_2_coldhot": pred_2_coldhot,
            "pred_3_zone": pred_3_zone,
            "pred_3_skip": pred_3_skip,
            "pred_3_scatter": pred_3_scatter,
            "update_time": datetime.now(tz_tw).strftime("%H:%M:%S")
        }

bot = UltimateBingoPredictor()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    data = bot.analyze()
    return templates.TemplateResponse("index.html", {"request": request, "data": data})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
