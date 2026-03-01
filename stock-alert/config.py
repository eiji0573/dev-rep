# config.py
import os
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

# ============================================================
# データソース設定
# ============================================================
# 'yfinance' または 'kabucom'（auカブコム証券API、口座開設後に切り替え）
DATA_SOURCE: str = os.getenv("DATA_SOURCE", "yfinance")

# ============================================================
# スキャン設定
# ============================================================
# 場中スキャンのインターバル（分単位）
SCAN_INTERVAL_MINUTES: int = int(os.getenv("SCAN_INTERVAL_MINUTES", "5"))

# 取引時間（日本時間）
TRADING_START_TIME: str = os.getenv("TRADING_START_TIME", "09:00")
TRADING_END_TIME: str   = os.getenv("TRADING_END_TIME", "15:30")

# ============================================================
# 急騰検知 デフォルト閾値（UI上で銘柄ごとに手動変更可能）
# ============================================================
# 前日終値からの変化率（%）
PRICE_CHANGE_FROM_PREV_CLOSE: float = float(os.getenv("PRICE_CHANGE_FROM_PREV_CLOSE", "3.0"))

# 当日始値からの変化率（%）
PRICE_CHANGE_FROM_OPEN: float = float(os.getenv("PRICE_CHANGE_FROM_OPEN", "5.0"))

# 過去20日平均出来高に対する倍率
VOLUME_RATIO: float = float(os.getenv("VOLUME_RATIO", "3.0"))

# RSIの過熱判断閾値
RSI_THRESHOLD: float = float(os.getenv("RSI_THRESHOLD", "70.0"))

# ボリンジャーバンドのシグマ値
BB_SIGMA: float = float(os.getenv("BB_SIGMA", "2.0"))

# ============================================================
# LINE Messaging API設定
# ============================================================
LINE_CHANNEL_ACCESS_TOKEN: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER_ID: str               = os.getenv("LINE_USER_ID", "")
