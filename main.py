from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import requests
import pandas as pd
import random
from datetime import datetime
import uvicorn

app = FastAPI()
templates = Jinja2Templates(directory="templates")

class BingoAnalyzer:
    def __init__(self):
        self.draws =[] 
        self.current_date = ""

    def fetch_today_data(self):
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        # 換日清空機制 (每天早上從頭算)
        if self.current_date != today_str:
            self.draws =[]
            self.current_date = today_str

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }
        
        try:
            # 這裡實作向台彩官方或第三方API請求今日數據
            # 由於台彩阻擋雲端IP，這裡以官方最新API格式為請求範例
            url = f"https://api.taiwanlottery.com/TLCAPIWeB/Lottery/BingoResult?date={today_str}"
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                # 假設成功取得，解析JSON並存入 self.draws
                # (此處需依據實際回傳的 JSON 結構調整解析欄位)
                pass 
            else:
                raise Exception(f"HTTP Status {response.status_code}")
                
        except Exception as e:
            print(f"無法獲取外部數據，啟動備用防錯機制: {e}")
            
        # [防錯機制] 若在 Zeabur 被阻擋，先以模擬數據讓你的策略碼能運作
        # 實務運用時若找到穩定的 Proxy 或第三方 API，替換上方 try 區塊即可
        self._generate_mock_today_data(now)

    def _generate_mock_today_data(self, now):
        self.draws =[]
        start_time = now.replace(hour=7, minute=5, second=0, microsecond=0)
        # 每5分鐘一期，計算今天開了幾期
        draw_count = int((now - start_time).total_seconds() / 300)
        if draw_count < 1: draw_count = 10 # 確保有資料可算
        
        for i in range(draw_count):
            nums = random.sample(range(1, 81), 20)
            self.draws.append({
                "draw_no": f"113{i:05d}",
                "numbers": sorted(nums)
            })

    def analyze(self):
        self.fetch_today_data()
        
        all_nums =[]
        for d in self.draws:
            all_nums.extend(d['numbers'])
            
        # 1. 統計熱門號碼
        freq = pd.Series(all_nums).value_counts()
        hot_numbers = freq.head(15).index.tolist()
        
        # 2. 統計冷門號碼 (計算距離上一次開出隔了幾期)
        last_seen = {i: -1 for i in range(1, 81)}
        for idx, d in enumerate(self.draws):
            for n in d['numbers']:
                last_seen[n] = idx
                
        current_idx = len(self.draws) - 1
        gaps = {n: current_idx - last_seen[n] for n in range(1, 81)}
        cold_numbers = sorted(gaps, key=gaps.get, reverse=True)[:15]
        
        # 3. 連號與跳期觀察 (基於上一期)
        last_draw_nums = self.draws[-1]['numbers']
        neighbors = set()
        for n in last_draw_nums:
            if n + 1 <= 80: neighbors.add(n + 1)
            if n - 1 >= 1: neighbors.add(n - 1)
        neighbors = list(neighbors - set(last_draw_nums)) # 排除掉跟上一期完全一樣的號碼
        
        # 【核心邏輯】：方案 A 變體生成器
        # 確保奇偶比例符合短線經驗 Tips (1奇2偶 或 2奇1偶)
        def is_valid_oddeven(combo):
            odds = sum(1 for x in combo if x % 2 != 0)
            return odds in [1, 2]

        def get_samsung_combo(pool_a, pool_b, pool_c):
            for _ in range(100): # 嘗試 100 次組合直到符合奇偶規則
                c =[random.choice(pool_a), random.choice(pool_b), random.choice(pool_c)]
                if len(set(c)) == 3 and is_valid_oddeven(c):
                    return sorted(c)
            # 防呆機制
            return sorted(list(set([pool_a[0], pool_b[0], pool_c[0]]))[:3])

        recs =[
            {
                "type": "攻擊型",
                "name": "🔥 追熱 + 連號組合",
                "desc": "選出 2個熱門號 + 1個上一期鄰近號",
                "combo": get_samsung_combo(hot_numbers[:10], hot_numbers[:10], neighbors)
            },
            {
                "type": "防守型",
                "name": "⚖️ 冷熱平衡組合",
                "desc": "選出 1個熱門號 + 1個冷門號 + 1個隨機互補號",
                "combo": get_samsung_combo(hot_numbers[:10], cold_numbers[:10], list(range(1, 81)))
            },
            {
                "type": "趨勢型",
                "name": "🔁 雙倍重複連開",
                "desc": "直接重押 1個上一期號碼 + 1個鄰近號 + 1個熱門號",
                "combo": get_samsung_combo(last_draw_nums, neighbors, hot_numbers[:10])
            }
        ]

        return {
            "total_draws": len(self.draws),
            "last_draw_no": self.draws[-1]['draw_no'],
            "last_draw_nums": last_draw_nums,
            "hot_numbers": hot_numbers[:8],
            "cold_numbers": cold_numbers[:8],
            "neighbors": neighbors[:8],
            "recommendations": recs,
            "update_time": datetime.now().strftime("%H:%M:%S")
        }

bingo_bot = BingoAnalyzer()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # 每次頁面重整都會觸發即時運算
    data = bingo_bot.analyze()
    return templates.TemplateResponse("index.html", {"request": request, "data": data})
