# data/yfinance_fetcher.py
import yfinance as yf
import pandas as pd

from data.base_fetcher import BaseFetcher, Timeframe

# yfinanceの制限により代替となる足種
LIMITED_TIMEFRAMES = {
    Timeframe.SECOND,
    Timeframe.MINUTE_1,
    Timeframe.MINUTE_5,
    Timeframe.MINUTE_10,
}

# Timeframe → yfinance interval マッピング
TIMEFRAME_INTERVAL_MAP: dict[Timeframe, str] = {
    Timeframe.SECOND:    "15m",  # 代替: 15分足
    Timeframe.MINUTE_1:  "15m",  # 代替: 15分足
    Timeframe.MINUTE_5:  "15m",  # 代替: 15分足
    Timeframe.MINUTE_10: "15m",  # 代替: 15分足
    Timeframe.MINUTE_15: "15m",
    Timeframe.DAY:       "1d",
    Timeframe.WEEK:      "1wk",
    Timeframe.MONTH:     "1mo",
}

# 空のOHLCVデータフレームのテンプレート
EMPTY_OHLCV = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])


class YfinanceFetcher(BaseFetcher):
    """
    yfinanceから株価データを取得するクラス。
    15分未満の足種はデータソースの制限により15分足で代替表示される。
    """
    is_limited: bool = True

    def is_timeframe_substituted(self, timeframe: Timeframe) -> bool:
        """指定の足種が15分足に代替されるかどうかを返す。"""
        return timeframe in LIMITED_TIMEFRAMES

    def get_ohlcv(self, ticker: str, timeframe: Timeframe, period: str) -> pd.DataFrame:
        """
        yfinanceからOHLCVデータを取得する。

        Args:
            ticker: 銘柄コード（例: "7203"）。末尾の".T"は自動付加される。
            timeframe: 取得したい足種。15分未満は15分足で代替される。
            period: 取得期間（例: "1mo", "3mo", "1y"）

        Returns:
            OHLCVデータのDataFrame。取得失敗時は空のDataFrameを返す。
        """
        # 日本株ティッカーに".T"を付加
        yf_ticker = f"{ticker}.T" if not ticker.endswith(".T") else ticker

        # 足種をyfinanceのintervalに変換
        interval = TIMEFRAME_INTERVAL_MAP.get(timeframe)
        if interval is None:
            print(f"Error: Unsupported timeframe: {timeframe}")
            return EMPTY_OHLCV.copy()

        try:
            data = yf.download(
                tickers=yf_ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,  # 株式分割・配当を自動調整
            )

            if data.empty:
                print(f"Warning: {yf_ticker} のデータが取得できませんでした（足種: {timeframe.label}, 期間: {period}）")
                return EMPTY_OHLCV.copy()

            # yfinance 新バージョンではMultiIndexになる場合があるためフラット化
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            # 必要なカラムのみ抽出して返す
            available_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in data.columns]
            return data[available_cols]

        except Exception as e:
            print(f"Error: {yf_ticker} のデータ取得中にエラーが発生しました: {e}")
            return EMPTY_OHLCV.copy()
