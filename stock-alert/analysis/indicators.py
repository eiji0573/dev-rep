# analysis/indicators.py
import pandas as pd
import pandas_ta as ta


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    OHLCVデータにテクニカル指標を追加する。

    Args:
        df: OHLCVデータ（columns: Open, High, Low, Close, Volume）

    Returns:
        テクニカル指標を追加したDataFrame。
        入力が空の場合はそのまま返す。
    """
    if df.empty:
        print("Warning: 入力DataFrameが空のため、テクニカル指標を計算できません。")
        return df.copy()

    df = df.copy()

    # --- 移動平均線（SMA: Simple Moving Average）---
    df["SMA_5"]  = ta.sma(df["Close"], length=5)   # 短期
    df["SMA_25"] = ta.sma(df["Close"], length=25)  # 中期
    df["SMA_75"] = ta.sma(df["Close"], length=75)  # 長期

    # --- 指数移動平均線（EMA: Exponential Moving Average）---
    df["EMA_5"]  = ta.ema(df["Close"], length=5)   # 短期
    df["EMA_25"] = ta.ema(df["Close"], length=25)  # 中期

    # --- ボリンジャーバンド（期間20, 2σ）---
    bbands = ta.bbands(df["Close"], length=20, std=2)
    if bbands is not None:
        df["BB_UPPER"] = bbands.iloc[:, 2]  # 上バンド（+2σ）
        df["BB_MIDDLE"] = bbands.iloc[:, 1]  # 中央バンド（SMA20）
        df["BB_LOWER"] = bbands.iloc[:, 0]  # 下バンド（-2σ）

    # --- RSI（期間14）---
    df["RSI_14"] = ta.rsi(df["Close"], length=14)

    # --- MACD（12, 26, 9）---
    macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)
    if macd is not None:
        df["MACD"]        = macd.iloc[:, 0]  # MACDライン
        df["MACD_SIGNAL"] = macd.iloc[:, 2]  # シグナルライン
        df["MACD_HIST"]   = macd.iloc[:, 1]  # ヒストグラム

    # --- 出来高移動平均（20日）---
    df["VOLUME_SMA_20"] = ta.sma(df["Volume"], length=20)

    return df


def detect_golden_cross(df: pd.DataFrame, short_col: str = "SMA_5", long_col: str = "SMA_25") -> pd.Series:
    """
    ゴールデンクロス（短期MAが長期MAを上抜け）を検出する。

    Args:
        df: テクニカル指標付きDataFrame
        short_col: 短期移動平均のカラム名
        long_col: 長期移動平均のカラム名

    Returns:
        ゴールデンクロス発生時にTrueのbool Series
    """
    if short_col not in df.columns or long_col not in df.columns:
        return pd.Series(False, index=df.index)

    # 前の足では短期 < 長期、現在の足では短期 > 長期
    prev_short = df[short_col].shift(1)
    prev_long = df[long_col].shift(1)
    golden_cross = (prev_short <= prev_long) & (df[short_col] > df[long_col])
    return golden_cross
