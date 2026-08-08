import time
import math
from collections import deque
from typing import Optional


class StressCalculator:
    """
    A simple stress calculator based on heart rate data. 
    It uses a sliding window of recent heart rate samples to compute a stress index ranging from 0 to 60.
    """

    def __init__(self, window_size: int = 30, resting_hr: int = 70):
        self.window_size = window_size
        self.resting_hr = resting_hr
        self._timestamps: deque = deque(maxlen=window_size)
        self._heart_rates: deque = deque(maxlen=window_size)

    def reset(self):
        self._timestamps.clear()
        self._heart_rates.clear()

    def add_heart_rate(self, hr: int) -> int:
        """Add a new heart rate sample and return the current stress index (0~100)"""
        now = time.time()
        self._timestamps.append(now)
        self._heart_rates.append(hr)
        return self.calculate()

    def calculate(self) -> int:
        """Calculate the current stress index based on the data window"""
        if len(self._heart_rates) < 3:
            # Insufficient data, only use deviation from resting heart rate
            if not self._heart_rates:
                return 0
            avg_hr = sum(self._heart_rates) / len(self._heart_rates)
            return self._hr_baseline_score(avg_hr)

        hrs = list(self._heart_rates)

        # 1. 心率均值偏离静息值的分数（0~60）
        avg_hr = sum(hrs) / len(hrs)
        baseline_score = self._hr_baseline_score(avg_hr)

        # 2. 心率变异性分数（0~40）：波动越大压力越高
        # 使用相邻差值的标准差
        diffs = [abs(hrs[i] - hrs[i - 1]) for i in range(1, len(hrs))]
        if len(diffs) >= 2:
            mean_diff = sum(diffs) / len(diffs)
            variance = sum((d - mean_diff) ** 2 for d in diffs) / len(diffs)
            std_diff = math.sqrt(variance)
        else:
            std_diff = abs(hrs[0] - hrs[-1]) if len(hrs) >= 2 else 0

        # 将标准差映射到 0~40
        # std=0 -> 0, std>=8 -> 40，线性映射
        hrv_score = min(40, int((std_diff / 8.0) * 40))

        total = baseline_score + hrv_score
        total = min(100, max(0, total))

        # 如果心率特别高，直接提高分数
        if avg_hr >= 140:
            total = max(total, 75)
        if avg_hr >= 170:
            total = max(total, 90)

        return int(total)

    def _hr_baseline_score(self, avg_hr: float) -> int:
        """
        Calculate a score based on how much the average heart rate deviates from the resting heart rate.
        """
        deviation = avg_hr - self.resting_hr
        if deviation <= 0:
            # low: 0~5
            return max(0, int(5 + deviation / 5.0))
        elif deviation <= 15:
            # mild: 5~25
            return int(5 + (deviation / 15.0) * 20)
        elif deviation <= 40:
            # mid: 25~50
            return int(25 + ((deviation - 15) / 25.0) * 25)
        else:
            # high: 50~60
            return min(60, int(50 + ((deviation - 40) / 30.0) * 10))
