# analysis/detector.py
import logging
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

import config
from analysis.indicators import add_technical_indicators, detect_golden_cross
from data.base_fetcher import BaseFetcher, Timeframe

# ロガー設定（ライブラリモジュールのため basicConfig は呼ばない）
logger = logging.getLogger(__name__)


@dataclass
class SurgeResult:
    """株価急騰検知の結果を格納するデータクラス。"""

    ticker: str         # 銘柄コード
    detected: bool      # 急騰検知フラグ
    price_change_prev_close: float  # 前日終値比変化率(%)
    price_change_open: float        # 当日始値比変化率(%)
    volume_ratio: float             # 出来高比率（直近出来高 / VOLUME_SMA_20）
    rsi: float                      # RSI_14 の最新値（NaN の場合は 0.0）
    golden_cross: bool              # 直近のゴールデンクロス発生フラグ
    bb_breakout: bool               # ボリンジャーバンド上抜けフラグ（BB_UPPER 超え）
    latest_close: float             # 最新終値
    timestamp: str                  # 検知時刻（ISO 形式）


def detect_surge(
    ticker: str,
    df: pd.DataFrame,
    price_from_prev_close: float = 3.0,
    price_from_open: float = 5.0,
    volume_ratio_threshold: float = 3.0,
    rsi_threshold: float = 70.0,
    bb_sigma: float = 2.0,
) -> SurgeResult:
    """
    OHLCVデータから株価急騰を検知する。

    日足・分足どちらでも動作する。分足の場合は日付ベースで
    前日終値・当日始値を正しく特定する。

    Args:
        ticker: 銘柄コード。
        df: OHLCVデータ（columns: Open, High, Low, Close, Volume）。
            テクニカル指標は関数内で付与する。
        price_from_prev_close: 前日終値比変化率の閾値(%)。
        price_from_open: 当日始値比変化率の閾値(%)。
        volume_ratio_threshold: 出来高比率の閾値。
        rsi_threshold: RSI 閾値（現状は情報として記録のみ、判定には未使用）。
        bb_sigma: BB 判定に用いるシグマ値（情報として記録のみ）。

    Returns:
        SurgeResult: 急騰検知結果。
    """
    # データが不十分な場合（前日終値の取得に最低2行必要）
    if df.empty or len(df) < 2:
        latest_close = float(df["Close"].iloc[-1]) if not df.empty else 0.0
        timestamp = (
            df.index[-1].isoformat()
            if not df.empty
            else datetime.now().isoformat()
        )
        logger.debug(
            f"銘柄 {ticker}: データ不足 (rows={len(df)})。デフォルト結果を返します。"
        )
        return SurgeResult(
            ticker=ticker,
            detected=False,
            price_change_prev_close=0.0,
            price_change_open=0.0,
            volume_ratio=0.0,
            rsi=0.0,
            golden_cross=False,
            bb_breakout=False,
            latest_close=latest_close,
            timestamp=timestamp,
        )

    # テクニカル指標を付与（元の DataFrame を汚さないよう copy を渡す）
    df_with_ta = add_technical_indicators(df.copy())

    latest = df_with_ta.iloc[-1]
    latest_close = float(latest["Close"])
    timestamp = df_with_ta.index[-1].isoformat()

    # ----------------------------------------------------------------
    # 前日終値・当日始値を日付ベースで特定
    # ----------------------------------------------------------------
    has_date_index = hasattr(df_with_ta.index[-1], "date")

    if has_date_index:
        latest_date = df_with_ta.index[-1].date()

        # 最新日より前の行 → 前日のデータ
        prev_df = df_with_ta[df_with_ta.index.date < latest_date]
        if not prev_df.empty:
            prev_day_close = float(prev_df.iloc[-1]["Close"])
        else:
            # 全行が同日（最初の1日分のみ）→ iloc[-2] で代用
            prev_day_close = float(df_with_ta.iloc[-2]["Close"])

        # 最新日のみの行 → 当日の始値は最初のローソク足の Open
        today_df = df_with_ta[df_with_ta.index.date == latest_date]
        current_day_open = (
            float(today_df.iloc[0]["Open"]) if not today_df.empty else float(latest["Open"])
        )
    else:
        # タイムゾーン情報がない場合のフォールバック（日足を想定）
        prev_day_close = float(df_with_ta.iloc[-2]["Close"])
        current_day_open = float(latest["Open"])

    # ----------------------------------------------------------------
    # 各指標の計算
    # ----------------------------------------------------------------

    # 前日終値比変化率 (%)
    price_change_prev_close = 0.0
    if prev_day_close > 0:
        price_change_prev_close = (latest_close - prev_day_close) / prev_day_close * 100

    # 当日始値比変化率 (%)
    price_change_open = 0.0
    if current_day_open > 0:
        price_change_open = (latest_close - current_day_open) / current_day_open * 100

    # 出来高比率（直近出来高 / VOLUME_SMA_20）
    volume_ratio = 0.0
    latest_volume = latest["Volume"]
    volume_sma_20 = latest.get("VOLUME_SMA_20", np.nan)
    if not (pd.isna(volume_sma_20) or volume_sma_20 <= 0):
        volume_ratio = float(latest_volume) / float(volume_sma_20)
    else:
        logger.debug(f"銘柄 {ticker}: VOLUME_SMA_20 が NaN または 0。volume_ratio=0.0 として扱います。")

    # RSI（NaN の場合は 0.0）
    rsi_raw = latest.get("RSI_14", np.nan)
    rsi = 0.0 if pd.isna(rsi_raw) else float(rsi_raw)

    # ゴールデンクロス（直近の発生フラグ）
    gc_series = detect_golden_cross(df_with_ta)
    golden_cross = bool(gc_series.iloc[-1]) if not gc_series.empty else False

    # ボリンジャーバンド上抜け（indicators.py は BB_UPPER 固定で生成）
    bb_upper_raw = latest.get("BB_UPPER", np.nan)
    bb_breakout = bool(not pd.isna(bb_upper_raw) and latest_close > float(bb_upper_raw))

    # ----------------------------------------------------------------
    # 急騰判定
    # ----------------------------------------------------------------
    # 価格変動条件: 前日終値比 OR 当日始値比のいずれかが閾値以上
    price_condition = (
        price_change_prev_close >= price_from_prev_close
        or price_change_open >= price_from_open
    )
    # 出来高条件: 出来高比率が閾値以上
    volume_condition = volume_ratio >= volume_ratio_threshold

    detected = price_condition and volume_condition

    return SurgeResult(
        ticker=ticker,
        detected=detected,
        price_change_prev_close=price_change_prev_close,
        price_change_open=price_change_open,
        volume_ratio=volume_ratio,
        rsi=rsi,
        golden_cross=golden_cross,
        bb_breakout=bb_breakout,
        latest_close=latest_close,
        timestamp=timestamp,
    )


def scan_watchlist(
    watchlist: list[dict],
    fetcher: BaseFetcher,
) -> list[SurgeResult]:
    """
    ウォッチリストをスキャンし、急騰が検知された銘柄を返す。

    Args:
        watchlist: ui/watchlist.py の render_watchlist() が返すリスト。
            各要素の形式::

                {
                    "ticker": "7203",
                    "price_change_from_prev_close": 3.0,
                    "price_change_from_open": 5.0,
                    "volume_ratio": 3.0,
                }

        fetcher: BaseFetcher のインスタンス（YfinanceFetcher など）。

    Returns:
        detected=True の銘柄の SurgeResult リスト（急騰なしの場合は空リスト）。
    """
    results: list[SurgeResult] = []

    for item in watchlist:
        ticker = item.get("ticker")
        if not ticker:
            logger.warning(f"ウォッチリスト項目に 'ticker' キーがありません: {item}")
            continue

        try:
            # period="5d" で取得することで前日終値の計算に必要なデータを確保する
            df = fetcher.get_ohlcv(ticker, Timeframe.MINUTE_15, period="5d")

            if df.empty:
                logger.info(f"銘柄 {ticker}: OHLCVデータが空です。スキップします。")
                continue

            result = detect_surge(
                ticker=ticker,
                df=df,
                # watchlist.py の戻り値キーに合わせて取得、未設定時は config デフォルト値
                price_from_prev_close=item.get(
                    "price_change_from_prev_close", config.PRICE_CHANGE_FROM_PREV_CLOSE
                ),
                price_from_open=item.get(
                    "price_change_from_open", config.PRICE_CHANGE_FROM_OPEN
                ),
                volume_ratio_threshold=item.get("volume_ratio", config.VOLUME_RATIO),
                rsi_threshold=config.RSI_THRESHOLD,  # watchlist には未公開、config から取得
                bb_sigma=config.BB_SIGMA,             # watchlist には未公開、config から取得
            )

            # 急騰検知された銘柄のみ結果リストに追加
            if result.detected:
                results.append(result)

        except Exception as e:
            logger.error(f"銘柄 {ticker} の処理中にエラーが発生しました: {e}")
            continue  # 例外が発生してもスキャンを継続する

    return results
