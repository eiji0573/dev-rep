# data/base_fetcher.py
from abc import ABC, abstractmethod
from enum import Enum
from typing import ClassVar
import pandas as pd


class Timeframe(Enum):
    """データ取得の足種を定義するEnum。"""
    SECOND = "1s"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_10 = "10m"
    MINUTE_15 = "15m"
    DAY = "1d"
    WEEK = "1wk"
    MONTH = "1mo"

    @property
    def label(self) -> str:
        """UI表示用ラベル。"""
        labels = {
            "1s": "秒足",
            "1m": "1分足",
            "5m": "5分足",
            "10m": "10分足",
            "15m": "15分足",
            "1d": "日足",
            "1wk": "週足",
            "1mo": "月足",
        }
        return labels.get(self.value, self.value)


class BaseFetcher(ABC):
    """
    株価データ取得の抽象基底クラス。
    このクラスを継承して、具体的なデータソースごとの取得ロジックを実装する。
    """
    # データソースが15分未満の足種をサポートしない場合はTrueを設定する。
    # UIでの注記表示に使用される。
    is_limited: ClassVar[bool] = False

    @abstractmethod
    def get_ohlcv(self, ticker: str, timeframe: Timeframe, period: str) -> pd.DataFrame:
        """
        OHLCVデータを取得する抽象メソッド。

        Args:
            ticker: 銘柄コード（例: "7203"）
            timeframe: 取得したい足種
            period: データの取得期間（例: "1mo", "3mo", "1y"）

        Returns:
            OHLCVデータのDataFrame（columns: Open, High, Low, Close, Volume）
            取得失敗時は空のDataFrameを返す。
        """
        pass

    @property
    def is_timeframe_limited(self) -> bool:
        """このデータソースが15分未満の足種を代替表示するかどうかを返す。"""
        return self.__class__.is_limited
