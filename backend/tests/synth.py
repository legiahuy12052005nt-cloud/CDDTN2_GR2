"""Sinh bộ dữ liệu tổng hợp đúng định dạng Reviews.csv để kiểm thử pipeline (không cần dữ liệu thật)."""
import numpy as np
import pandas as pd

POS = ["delicious", "great taste", "love it", "fresh and tasty", "perfect snack", "highly recommend", "excellent flavor", "my kids love"]
NEG = ["stale", "tastes awful", "arrived broken", "expired date", "too sweet", "weak coffee", "made my dog sick", "overpriced", "box was crushed"]
NEU = ["it is okay", "average taste", "nothing special", "not bad not great", "decent but pricey"]
FOOD = ["coffee", "tea", "cookies", "dog food", "chocolate", "chips", "pasta", "honey"]


def make(n=4000, n_products=30, months=60, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2008-01-01")
    rows = []
    pids = [f"B00{i:07d}" for i in range(n_products)]
    for i in range(n):
        p = pids[int(rng.integers(0, n_products))] if i % 3 else pids[i % 5]
        m = int(rng.integers(0, months))
        # sản phẩm 0 xấu dần ở 6 tháng cuối để có cảnh báo rủi ro
        drift = (p == pids[0] and m >= months - 4)
        score = int(rng.choice([1, 2, 3, 4, 5], p=[.45, .2, .1, .1, .15] if drift else [.08, .06, .09, .17, .6]))
        bag = NEG if score <= 2 else (NEU if score == 3 else POS)
        food = FOOD[int(rng.integers(0, len(FOOD)))]
        words = " ".join(rng.choice(bag, 3)) + f" this {food} " + " ".join(rng.choice(bag, 2))
        t = start + pd.DateOffset(months=m) + pd.Timedelta(days=int(rng.integers(0, 27)))
        rows.append({"Id": i + 1, "ProductId": p, "UserId": f"U{int(rng.integers(0, 900))}", "ProfileName": "x",
                     "HelpfulnessNumerator": 0, "HelpfulnessDenominator": 1, "Score": score, "Time": int(t.timestamp()),
                     "Summary": bag[int(rng.integers(0, len(bag)))].title(), "Text": f"I bought {food}. {words}. Review number {i}."})
    return pd.DataFrame(rows)
