# ui/watchlist.py
import os
import re
import sys
import logging
from typing import Any

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from ui.utils import get_company_name

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------
# セッションステート
# ----------------------------------------------------------------

def _default_settings() -> dict[str, Any]:
    """銘柄ごとのデフォルト設定を返す。"""
    return {
        "price_change_from_prev_close": float(config.PRICE_CHANGE_FROM_PREV_CLOSE),
        "price_change_from_open":       float(config.PRICE_CHANGE_FROM_OPEN),
        "volume_ratio":                 float(config.VOLUME_RATIO),
        "enabled":                      True,
        "filter_rsi":                   False,
        "filter_bb":                    False,
        "filter_gc":                    False,
        "momentum_period":              10,   # Phase 6 予定
        "roc_period":                   10,   # Phase 6 予定
        "volume_accel_window":          5,    # Phase 6 予定
    }


def _init_session_state() -> None:
    """
    新形式のセッションステートを初期化する。
    旧形式（watchlist_tickers / watchlist_thresholds）が存在する場合はマイグレーションする。
    """
    if "watchlist_settings" not in st.session_state:
        st.session_state.watchlist_settings: dict[str, dict] = {}

    if "watchlist_selected" not in st.session_state:
        st.session_state.watchlist_selected: set[str] = set()

    # 旧形式マイグレーション
    if "watchlist_tickers" in st.session_state and "watchlist_thresholds" in st.session_state:
        logger.info("旧形式のウォッチリストを新形式にマイグレーションします。")
        old_tickers: list[str] = st.session_state.watchlist_tickers
        old_thresholds: dict = st.session_state.watchlist_thresholds

        for ticker in old_tickers:
            if ticker not in st.session_state.watchlist_settings:
                s = _default_settings()
                old = old_thresholds.get(ticker, {})
                s["price_change_from_prev_close"] = float(old.get("prev_close", s["price_change_from_prev_close"]))
                s["price_change_from_open"]       = float(old.get("open",       s["price_change_from_open"]))
                s["volume_ratio"]                 = float(old.get("volume",     s["volume_ratio"]))
                st.session_state.watchlist_settings[ticker] = s

        del st.session_state["watchlist_tickers"]
        del st.session_state["watchlist_thresholds"]
        logger.info("マイグレーション完了。旧キーを削除しました。")
        st.rerun()


# ----------------------------------------------------------------
# 銘柄操作
# ----------------------------------------------------------------

def _add_ticker(ticker: str) -> None:
    """ウォッチリストに銘柄を追加する。重複時は警告を表示。"""
    if ticker in st.session_state.watchlist_settings:
        st.warning(f"銘柄 {ticker} は既に登録済みです。")
        return
    st.session_state.watchlist_settings[ticker] = _default_settings()
    logger.info(f"銘柄 {ticker} を追加しました。")
    st.rerun()


def _remove_ticker(ticker: str) -> None:
    """ウォッチリストから銘柄を削除する。"""
    st.session_state.watchlist_settings.pop(ticker, None)
    st.session_state.watchlist_selected.discard(ticker)
    logger.info(f"銘柄 {ticker} を削除しました。")
    st.rerun()


# ----------------------------------------------------------------
# UI: 銘柄追加セクション
# ----------------------------------------------------------------

def _render_add_ticker_section() -> None:
    """銘柄コード入力と追加ボタンを表示する。"""
    with st.container(border=True):
        st.markdown("#### 銘柄を追加")
        col_input, col_btn, _col_space = st.columns([0.25, 0.08, 0.67])
        with col_input:
            raw = st.text_input(
                "銘柄コード（4桁の数字）",
                max_chars=4,
                placeholder="例: 7203",
                key="add_ticker_input",
            ).strip()
        with col_btn:
            st.write("")
            st.write("")
            is_valid = bool(raw and re.fullmatch(r"\d{4}", raw))
            if st.button("追加", type="primary", disabled=not is_valid, key="add_ticker_btn"):
                _add_ticker(raw)
        if raw and not is_valid:
            st.caption("⚠️ 4桁の数字で入力してください。")


# ----------------------------------------------------------------
# UI: 一括操作バー
# ----------------------------------------------------------------

def _render_bulk_action_bar() -> None:
    """一括操作バーを常時表示する。未選択時はボタンを無効化。"""
    selected: set[str] = st.session_state.watchlist_selected
    n = len(selected)
    has_selection = n > 0

    with st.container(border=True):
        col_label, col_on, col_off, col_del, col_clear = st.columns([2, 1, 1, 1, 1])

        rerun_needed = False

        with col_label:
            st.markdown(f"**{n} 件選択中**" if has_selection else "**（未選択）**")

        with col_on:
            if st.button("一括ON", key="bulk_on", disabled=not has_selection):
                for t in selected:
                    if t in st.session_state.watchlist_settings:
                        st.session_state.watchlist_settings[t]["enabled"] = True
                rerun_needed = True

        with col_off:
            if st.button("一括OFF", key="bulk_off", disabled=not has_selection):
                for t in selected:
                    if t in st.session_state.watchlist_settings:
                        st.session_state.watchlist_settings[t]["enabled"] = False
                rerun_needed = True

        with col_del:
            if st.button("一括削除", key="bulk_del", type="secondary",
                         disabled=not has_selection):
                for t in list(selected):
                    st.session_state.watchlist_settings.pop(t, None)
                st.session_state.watchlist_selected.clear()
                rerun_needed = True

        with col_clear:
            if st.button("選択解除", key="bulk_clear", disabled=not has_selection):
                st.session_state.watchlist_selected.clear()
                rerun_needed = True

        if rerun_needed:
            st.rerun()


# ----------------------------------------------------------------
# UI: Phase 6 予定セクション（グレーアウト）
# ----------------------------------------------------------------

def _render_phase6_section(ticker: str, settings: dict) -> None:
    """Phase 6 実装予定の早期検知スライダーをグレーアウトで表示する。"""
    with st.expander("🔒 早期検知（Phase 6 実装予定）", expanded=False):
        st.caption("これらの設定は Phase 6b で有効化されます。現在は値の保存のみ行います。")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.slider(
                "モメンタム期間",
                min_value=5, max_value=30, step=1,
                value=int(settings.get("momentum_period", 10)),
                key=f"momentum_{ticker}",
                disabled=True,
            )
        with col2:
            st.slider(
                "ROC 期間",
                min_value=5, max_value=30, step=1,
                value=int(settings.get("roc_period", 10)),
                key=f"roc_{ticker}",
                disabled=True,
            )
        with col3:
            st.slider(
                "出来高急増ウィンドウ",
                min_value=3, max_value=15, step=1,
                value=int(settings.get("volume_accel_window", 5)),
                key=f"vol_accel_{ticker}",
                disabled=True,
            )
        # Phase 6b 有効化時は disabled=True を削除し、以下の書き戻しコードを追加:
        # settings["momentum_period"]     = momentum_val
        # settings["roc_period"]          = roc_val
        # settings["volume_accel_window"] = vol_accel_val


# ----------------------------------------------------------------
# UI: 銘柄カード
# ----------------------------------------------------------------

def _render_stock_card(ticker: str, settings: dict) -> None:
    """1銘柄のカードUIをレンダリングする。"""
    with st.container(border=True):

        # --- ヘッダー行 ---
        c_chk, c_tog, c_name, c_badge, c_link, c_del = st.columns([0.5, 0.7, 3.5, 1.2, 1.0, 0.8])

        with c_chk:
            is_selected = ticker in st.session_state.watchlist_selected
            checked = st.checkbox(
                "", value=is_selected,
                key=f"sel_{ticker}",
                label_visibility="collapsed",
            )
            if checked:
                st.session_state.watchlist_selected.add(ticker)
            else:
                st.session_state.watchlist_selected.discard(ticker)

        with c_tog:
            enabled = st.toggle(
                "監視",
                value=settings["enabled"],
                key=f"enabled_{ticker}",
                label_visibility="collapsed",
            )
            settings["enabled"] = enabled

        with c_name:
            company = get_company_name(ticker)
            onoff_icon = "🟢" if settings["enabled"] else "⚪"
            st.markdown(f"{onoff_icon} **{ticker}** {company}")

        with c_badge:
            st.caption("📌 15分足推奨")

        with c_link:
            st.link_button(
                "Yahoo↗",
                f"https://finance.yahoo.co.jp/quote/{ticker}.T",
            )

        with c_del:
            if st.button("🗑 削除", key=f"del_{ticker}", type="secondary"):
                _remove_ticker(ticker)

        # --- Section 1: 急騰検知 閾値 ---
        st.markdown("**急騰検知 閾値**")
        s1c1, s1c2, s1c3 = st.columns(3)
        with s1c1:
            settings["price_change_from_prev_close"] = st.slider(
                "前日終値比（%）",
                min_value=0.5, max_value=20.0, step=0.5,
                value=float(settings["price_change_from_prev_close"]),
                key=f"pc_prev_{ticker}",
            )
        with s1c2:
            settings["price_change_from_open"] = st.slider(
                "当日始値比（%）",
                min_value=0.5, max_value=20.0, step=0.5,
                value=float(settings["price_change_from_open"]),
                key=f"pc_open_{ticker}",
            )
        with s1c3:
            settings["volume_ratio"] = st.slider(
                "出来高倍率",
                min_value=1.0, max_value=10.0, step=0.5,
                value=float(settings["volume_ratio"]),
                key=f"vol_{ticker}",
            )

        # --- Section 2: 誤検知削減フィルタ ---
        st.markdown("**誤検知削減（テクニカル指標フィルタ）**")
        st.caption("※ Phase 6a で発報判定への組み込みを検証予定")
        s2c1, s2c2, s2c3 = st.columns(3)
        with s2c1:
            settings["filter_rsi"] = st.checkbox(
                "RSI > 70",
                value=settings["filter_rsi"],
                key=f"f_rsi_{ticker}",
            )
        with s2c2:
            settings["filter_bb"] = st.checkbox(
                "BB 上抜け",
                value=settings["filter_bb"],
                key=f"f_bb_{ticker}",
            )
        with s2c3:
            settings["filter_gc"] = st.checkbox(
                "ゴールデンクロス",
                value=settings["filter_gc"],
                key=f"f_gc_{ticker}",
            )

        # --- Section 3: Phase 6 予定 ---
        _render_phase6_section(ticker, settings)


# ----------------------------------------------------------------
# メイン公開関数
# ----------------------------------------------------------------

def render_watchlist() -> list[dict[str, Any]]:
    """
    監視銘柄管理UIを表示し、enabled=True の銘柄リストを返す。

    Returns:
        有効銘柄のリスト（detector.py の scan_watchlist に渡す形式）。
        各要素の形式::

            {
                "ticker": "7203",
                "price_change_from_prev_close": 3.0,
                "price_change_from_open": 5.0,
                "volume_ratio": 3.0,
                "filter_rsi": False,
                "filter_bb": False,
                "filter_gc": False,
            }
    """
    _init_session_state()

    _render_add_ticker_section()

    st.divider()

    settings_map: dict[str, dict] = st.session_state.watchlist_settings
    total = len(settings_map)
    # トグルの現在値を st.session_state のウィジェットキーから直接読む
    # （カード描画前に settings["enabled"] を参照すると 1 フレーム遅れるため）
    enabled_count = sum(
        1 for t, s in settings_map.items()
        if st.session_state.get(f"enabled_{t}", s["enabled"])
    )
    st.markdown(f"#### 登録済み銘柄（{total} 件 / 監視中 {enabled_count} 件）")

    if not settings_map:
        st.info("銘柄が未登録です。上の入力欄から追加してください。")
        return []

    _render_bulk_action_bar()

    for ticker, settings in settings_map.items():
        _render_stock_card(ticker, settings)

    # enabled=True の銘柄のみ返す
    return [
        {
            "ticker":                       t,
            "price_change_from_prev_close": s["price_change_from_prev_close"],
            "price_change_from_open":       s["price_change_from_open"],
            "volume_ratio":                 s["volume_ratio"],
            "filter_rsi":                   s["filter_rsi"],
            "filter_bb":                    s["filter_bb"],
            "filter_gc":                    s["filter_gc"],
        }
        for t, s in settings_map.items()
        if s["enabled"]
    ]
