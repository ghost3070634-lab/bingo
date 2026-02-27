from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import requests
import pandas as pd
import random
from datetime import datetime, timezone, timedelta
import urllib3
import os
import uvicorn

# 1. 停用 Python 的 SSL 警告 (強行突破台彩憑證)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 2. 終極防呆：檢查是否有 templates 資料夾，沒有就自動建立並塞入警告檔，防止 502 當機
if not os.path.exists("templates"):
    os.makedirs("templates")
    with open("templates/index.html", "w", encoding="utf-8") as f:
        f.write("<h1 style='color:red;'>系統已成功啟動！<br>但你忘記把 index.html 放入 templates 資料夾中了，請回 GitHub 檢查！</h1>")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

class BingoAnalyzer:
    def __init__(self):
        self.draws =[] 
        self.current_date = ""

    def fetch_today_data(self):
        # 3. 強制設定為台灣時區 (UTC+8)，避免雲端主機時間錯亂
        tz_tw = timezone(timedelta(hours=8))
        now = datetime.now(tz_tw)
        today_str = now.strftime("%Y-%m-%d")
        
        if self.current_date != today_str:
            self.draws =[]
            self.current_date = today_str

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }
        
        url = f"https://api.taiwanlottery.com/TLCAPIWeB/Lottery/BingoResult?date={today_str}"
        try:
            # 關鍵修復：加入 verify=False 繞過憑證驗證
            response = requests.get(url, headers=headers, timeout=10, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                # 嘗試解析台彩 API 真實資料
                if "content" in data and "bingoResult" in data["content"]:
                    real_draws = []
                    for item in data["content"]["bingoResult"]:
                        # 嘗試抓取號碼欄位
                        nums_str = item.get("drawNumberSize", item.get("drawNumber", ""))
                        if nums_str:
                            nums = sorted([int(x) for x in nums_str.split(",") if x.isdigit()])
                            real_draws.append({
                                "draw_no": str(item.get("drawTerm", "未知")),
                                "numbers": nums
                            })
                    if real_draws:
                        # API 回傳通常是從新到舊，我們將其反轉為從舊到新
                        self.draws = list(reversed(real_draws))
                        return # 成功抓到資料，提早結束
        except Exception as e:
            print(f"真實數據抓取失敗，啟動備用機制: {e}")
            
        # 備用機制 (只在台彩完全當機或阻擋時執行)
        self._generate_mock_today_data(now)

    def _generate_mock_today_data(self, now):
        self.draws =[]
        # 以台灣時間早上 7:05 為基準點
        start_time = now.replace(hour=7, minute=5, second=0, microsecond=0)
        draw_count = int((now - start_time).total_seconds() / 300)
        
        # 確保期數合理 (避免半夜執行時變負數)
        if draw_count < 1: draw_count = 1
        if draw_count > 200: draw_count = 200
        
        for i in range(draw_count):
            nums = random.sample(range(1, 81), 20)
            self.draws.append({
                "draw_no": f"模擬期數-{i+1:03d}",
                "numbers": sorted(nums)
            })

    def analyze(self):
        self.fetch_today_data()
        
        all_nums =[]
        for d in self.draws:
            all_nums.extend(d['numbers'])
            
        # 統計熱門與冷門
        freq = pd.Series(all_nums).value_counts()
        hot_numbers = freq.head(15).index.tolist() if not freq.empty else list(range(1, 16))
        
        last_seen = {i: -1 for i in range(1, 81)}
        for idx, d in enumerate(self.draws):
            for n in d['numbers']:
                last_seen[n] = idx
                
        current_idx = len(self.draws) - 1
        gaps = {n: current_idx - last_seen[n] for n in range(1, 81)}
        cold_numbers = sorted(gaps, key=gaps.get, reverse=True)[:15]
        
        # 連號觀察
        last_draw_nums = self.draws[-1]['numbers'] if self.draws else random.sample(range(1, 81), 20)
        neighbors = set()
        for n in last_draw_nums:
            if n + 1 <= 80: neighbors.add(n + 1)
            if n - 1 >= 1: neighbors.add(n - 1)
        neighbors = list(neighbors - set(last_draw_nums))
        if not neighbors: neighbors = list(range(20, 30))

        # 三星組合邏輯
        def is_valid_oddeven(combo):
            odds = sum(1 for x in combo if x % 2 != 0)
            return odds in [1, 2]

        def get_samsung_combo(pool_a, pool_b, pool_c):
            for _ in range(100):
                c =[random.choice(pool_a), random.choice(pool_b), random.choice(pool_c)]
                if len(set(c)) == 3 and is_valid_oddeven(c):
                    return sorted(c)
            return sorted(list(set([pool_a[0], pool_b[0], pool_c[0]] + [1,2,3]))[:3])

        recs =[
            {"type": "攻擊型", "name": "🔥 追熱 + 連號組合", "desc": "選出 2個熱門號 + 1個上一期鄰近號", "combo": get_samsung_combo(hot_numbers[:10], hot_numbers[:10], neighbors)},
            {"type": "防守型", "name": "⚖️ 冷熱平衡組合", "desc": "選出 1個熱門號 + 1個冷門號 + 1個隨機互補號", "combo": get_samsung_combo(hot_numbers[:10], cold_numbers[:10], list(range(1, 81)))},
            {"type": "趨勢型", "name": "🔁 雙倍重複連開", "desc": "直接重押 1個上一期號碼 + 1個鄰近號 + 1個熱門號", "combo": get_samsung_combo(last_draw_nums, neighbors, hot_numbers[:10])}
        ]

        tz_tw = timezone(timedelta(hours=8))
        return {
            "total_draws": len(self.draws),
            "last_draw_no": self.draws[-1]['draw_no'] if self.draws else "無",
            "hot_numbers": hot_numbers[:8],
            "cold_numbers": cold_numbers[:8],
            "neighbors": neighbors[:8],
            "recommendations": recs,
            "update_time": datetime.now(tz_tw).strftime("%H:%M:%S")
        }

bingo_bot = BingoAnalyzer()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    data = bingo_bot.analyze()
    return templates.TemplateResponse("index.html", {"request": request, "data": data})

# 確保 Zeabur 絕對抓得到 Port
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
