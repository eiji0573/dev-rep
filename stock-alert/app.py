# app.py
import logging
import os
import sys

import streamlit as st

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(__file__))

import config
from analysis.detector import SurgeResult, scan_watchlist
from data.base_fetcher import BaseFetcher
from data.yfinance_fetcher import YfinanceFetcher
from scheduler.job import SurgeScanner, create_scanner_from_config
from ui.chart import render_chart
from ui.watchlist import render_watchlist

# ロガー設定（ライブラリモジュールのため basicConfig は呼ばない）
logger = logging.getLogger(__name__)


# ----------------------------------------------------------------
# データフェッチャー
# ----------------------------------------------------------------

def get_fetcher() -> BaseFetcher:
    """
    config.DATA_SOURCE に応じたデータ取得インスタンスを返す。
    将来的に auカブコム証券API に対応する場合はここに追加する。
    """
    if config.DATA_SOURCE == "yfinance":
        return YfinanceFetcher()
    else:
        raise NotImplementedError(f"未対応のデータソース: {config.DATA_SOURCE}")


# ----------------------------------------------------------------
# スキャナー初期化
# ----------------------------------------------------------------

def _init_scanner() -> None:
    """
    セッション初回のみ SurgeScanner を session_state に初期化する。
    失敗時は scanner=None とし、エ外は raise しない。
    """
    if "scanner" in st.session_state:
        return

    try:
        st.session_state.scanner: SurgeScanner | None = create_scanner_from_config([])
        st.session_state.scanner_running: bool = False
        st.session_state.last_surge_results: list[SurgeResult] = []
        logger.info("SurgeScanner を初期化しました。")
    except Exception as e:
        st.session_state.scanner = None
        st.session_state.scanner_running = False
        st.session_state.last_surge_results = []
        logger.error(f"SurgeScanner の初期化に失敗しました: {e}", exc_info=True)


# ----------------------------------------------------------------
# サイドバー: スキャナーコントロール
# ----------------------------------------------------------------

def _render_scanner_controls() -> None:
    """サイドバーに場中スキャンのコントロール UI を表示する。"""
    st.divider()
    st.subheader("🔍 場中スキャン")

    scanner: SurgeScanner | None = st.session_state.get("scanner")

    # スキャナー初期化エラー時
    if scanner is None:
        st.error("スキャナーの初期化に失敗しました。設定を確認してください。")
        return

    is_running: bool = st.session_state.get("scanner_running", False)

    # 状態表示
    if is_running:
        st.success("🟢 スキャン中")
        if st.button("⏹ スキャン停止", use_container_width=True, type="secondary"):
            try:
                scanner.stop()
                st.session_state.scanner_running = False
                logger.info("SurgeScanner を停止しました。")
            except Exception as e:
                logger.error(f"SurgeScanner の停止に失敗: {e}", exc_info=True)
                st.error("スキャナーの停止に失敗しました。")
            st.rerun()
    else:
        st.info("⚪ 停止中")
        if st.button("▶ スキャン開始", use_container_width=True, type="primary"):
            try:
                scanner.start()
                st.session_state.scanner_running = True
                logger.info("SurgeScanner を開始しました。")
            except Exception as e:
                logger.error(f"SurgeScanner の開始に失敗: {e}", exc_info=True)
                st.error("スキャナーの開始に失敗しました。")
            st.rerun()

    st.caption(
        f"間隔: **{config.SCAN_INTERVAL_MINUTES}分** / "
        f"{config.TRADING_START_TIME}〜{config.TRADING_END_TIME}"
    )


# ----------------------------------------------------------------
# スキャン結果表示
# ----------------------------------------------------------------

def _render_surge_results(results: list[SurgeResult]) -> None:
    """急騰スキャン結果をカード形式で表示する。"""
    if not results:
        st.info("急騰銘柄は見つかりませんでした。")
        return

    st.subheader(f"🚨 急騰検知: {len(results)} 銘柄")
    for r in results:
        with st.container(border=True):
            st.subheader(f"【急騰】{r.ticker}")

            # 4列メトリクス表示
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("前日終値比", f"{r.price_change_prev_close:+.2f}%")
            col2.metric("始値比",     f"{r.price_change_open:+.2f}%")
            col3.metric("出来高比",   f"{r.volume_ratio:.1f}倍")
            col4.metric("RSI",        f"{r.rsi:.1f}")

            # 追加シグナル
            signals = []
            if r.golden_cross:
                signals.append("📈 ゴールデンクロス発生")
            if r.bb_breakout:
                signals.append("🔺 BB上抜け")
            if signals:
                st.caption("  ".join(signals))

            st.caption(f"検知時刻: {r.timestamp}  /  終値: {r.latest_close:,.0f}円")


# ----------------------------------------------------------------
# メイン
# ----------------------------------------------------------------

def main() -> None:
    """Streamlit アプリのエントリーポイント。"""

    st.set_page_config(
        page_title="株価監視・急騰通知アプリ",
        page_icon="📈",
        layout="wide",
    )

    # --- サイドバー（ページ選択・データソース表示） ---
    with st.sidebar:
        st.title("📈 株価監視アプリ")
        st.divider()

        page = st.radio(
            "ページ選択",
            ["📊 チャート分析", "👀 監視銘柄管理"],
            label_visibility="collapsed",
        )

        st.divider()

        source_label = {
            "yfinance": "yfinance（15分遅延）",
            "kabucom":  "auカブコム証券API",
        }.get(config.DATA_SOURCE, config.DATA_SOURCE)
        st.caption(f"📡 データソース: **{source_label}**")

    # --- フェッチャー生成 ---
    fetcher = get_fetcher()

    # --- スキャナー初期化（セッション初回のみ） ---
    _init_scanner()

    # --- サイドバー: スキャナーコントロール ---
    with st.sidebar:
        _render_scanner_controls()

    # --- ページルーティング ---
    if page == "📊 チャート分析":
        ticker = st.sidebar.text_input(
            "銘柄コード（4桁）",
            value="7203",
            max_chars=4,
            placeholder="例: 7203",
        )
        if ticker:
            render_chart(ticker, fetcher)
        else:
            st.info("サイドバーから銘柄コードを入力してください。")

    elif page == "👀 監視銘柄管理":
        watchlist = render_watchlist()

        # スキャナーのウォッチリストを最新状態に同期
        scanner: SurgeScanner | None = st.session_state.get("scanner")
        if scanner is not None:
            scanner.update_watchlist(watchlist)

        st.divider()

        # --- 手動スキャン ---
        st.subheader("🔍 今すぐスキャン")
        if not watchlist:
            st.warning("監視銘柄を登録してからスキャンを実行してください。")
        else:
            if st.button("🔍 今すぐスキャン", type="primary"):
                with st.spinner(f"{len(watchlist)} 銘柄をスキャン中..."):
                    results = scan_watchlist(watchlist, fetcher)
                    st.session_state.last_surge_results = results
                    logger.info(f"手動スキャン完了: 急騰={len(results)} 件")
                st.rerun()

            # 前回スキャン結果を表示
            _render_surge_results(st.session_state.get("last_surge_results", []))


if __name__ == "__main__":
    main()
