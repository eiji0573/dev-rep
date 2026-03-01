# ui/watchlist.py
import re
import sys
import os
from typing import Any

import streamlit as st

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config

# --- Session State 初期化ヘルパー ---
def _init_session_state() -> None:
    """監視銘柄管理に必要なSession Stateを初期化する。"""
    if "watchlist_tickers" not in st.session_state:
        st.session_state.watchlist_tickers: list[str] = []
    if "watchlist_thresholds" not in st.session_state:
        st.session_state.watchlist_thresholds: dict[str, dict[str, float]] = {}


def _default_threshold() -> dict[str, float]:
    """config.pyのデフォルト閾値を返す。"""
    return {
        "prev_close": config.PRICE_CHANGE_FROM_PREV_CLOSE,
        "open":       config.PRICE_CHANGE_FROM_OPEN,
        "volume":     config.VOLUME_RATIO,
    }


def _add_ticker(ticker: str) -> None:
    """監視銘柄を追加する。"""
    if ticker in st.session_state.watchlist_tickers:
        st.warning(f"銘柄 {ticker} はすでに登録済みです。")
        return
    st.session_state.watchlist_tickers.append(ticker)
    st.session_state.watchlist_thresholds[ticker] = _default_threshold()
    st.success(f"銘柄 {ticker} を追加しました。")
    st.rerun()


def _remove_ticker(ticker: str) -> None:
    """監視銘柄を削除する。"""
    st.session_state.watchlist_tickers.remove(ticker)
    st.session_state.watchlist_thresholds.pop(ticker, None)
    st.rerun()


def render_watchlist() -> list[dict[str, Any]]:
    """
    監視銘柄の登録・管理画面をレンダリングする。

    Returns:
        現在の監視銘柄と閾値のリスト。
        各要素: {ticker, price_change_from_prev_close, price_change_from_open, volume_ratio}
    """
    _init_session_state()

    st.header("👀 監視銘柄管理")

    # --- 銘柄追加 ---
    with st.container(border=True):
        st.subheader("銘柄を追加")
        col1, col2 = st.columns([0.75, 0.25])
        with col1:
            ticker_input = st.text_input(
                "銘柄コード（4桁の数字）",
                max_chars=4,
                placeholder="例: 7203",
                key="ticker_input",
            )
        with col2:
            st.write("")  # ラベル分のスペース調整
            st.write("")
            is_valid = bool(ticker_input and re.fullmatch(r"\d{4}", ticker_input))
            if st.button("追加", disabled=not is_valid, type="primary"):
                _add_ticker(ticker_input)

        if ticker_input and not is_valid:
            st.caption("⚠️ 銘柄コードは4桁の数字で入力してください。")

    st.divider()

    # --- 登録済み銘柄一覧 ---
    st.subheader(f"登録済み銘柄（{len(st.session_state.watchlist_tickers)}件）")

    if not st.session_state.watchlist_tickers:
        st.info("監視銘柄が登録されていません。上から銘柄を追加してください。")
    else:
        for ticker in st.session_state.watchlist_tickers:
            thresholds = st.session_state.watchlist_thresholds.get(ticker, _default_threshold())

            with st.expander(f"📌 {ticker}", expanded=False):
                col_title, col_del = st.columns([0.85, 0.15])
                with col_del:
                    if st.button("🗑️ 削除", key=f"del_{ticker}", type="secondary"):
                        _remove_ticker(ticker)

                st.markdown("**急騰検知 閾値設定**")

                prev_close = st.slider(
                    "前日終値比（%）",
                    min_value=0.0, max_value=20.0,
                    value=thresholds["prev_close"],
                    step=0.1, format="%.1f%%",
                    key=f"prev_close_{ticker}",
                )
                from_open = st.slider(
                    "当日始値比（%）",
                    min_value=0.0, max_value=30.0,
                    value=thresholds["open"],
                    step=0.1, format="%.1f%%",
                    key=f"open_{ticker}",
                )
                volume_ratio = st.slider(
                    "出来高倍率（過去20日平均比）",
                    min_value=1.0, max_value=10.0,
                    value=thresholds["volume"],
                    step=0.1, format="%.1f倍",
                    key=f"volume_{ticker}",
                )

                # 変更値をSession Stateに保存
                st.session_state.watchlist_thresholds[ticker] = {
                    "prev_close": prev_close,
                    "open":       from_open,
                    "volume":     volume_ratio,
                }

    # --- 戻り値の生成 ---
    return [
        {
            "ticker":                     t,
            "price_change_from_prev_close": st.session_state.watchlist_thresholds.get(t, _default_threshold())["prev_close"],
            "price_change_from_open":       st.session_state.watchlist_thresholds.get(t, _default_threshold())["open"],
            "volume_ratio":                 st.session_state.watchlist_thresholds.get(t, _default_threshold())["volume"],
        }
        for t in st.session_state.watchlist_tickers
    ]
