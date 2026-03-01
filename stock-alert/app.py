# app.py
import logging
import os
import sys

import streamlit as st
import streamlit.components.v1 as components

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(__file__))

import config
from analysis.detector import SurgeResult, scan_watchlist
from data.base_fetcher import BaseFetcher
from data.yfinance_fetcher import YfinanceFetcher
from scheduler.job import SurgeScanner, create_scanner_from_config
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
    失敗時は scanner=None とし、例外は raise しない。
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
# CSS / JS インジェクション
# ----------------------------------------------------------------

def _inject_cancel_label() -> None:
    """「やめて」ボタンのラベルを「キャンセル」に置換する。"""
    components.html(
        """
        <script>
        (function () {
            function replaceLabel() {
                var buttons = window.parent.document.querySelectorAll("button");
                buttons.forEach(function (btn) {
                    if (btn.textContent.trim() === "やめて") {
                        btn.textContent = "キャンセル";
                    }
                });
            }
            replaceLabel();
            var observer = new MutationObserver(replaceLabel);
            observer.observe(window.parent.document.body, {
                childList: true, subtree: true, characterData: true,
            });
        })();
        </script>
        """,
        height=0,
    )


def _inject_sidebar_hide() -> None:
    """左サイドバーを非表示にし、全体の余白をコンパクトにする CSS を注入する。"""
    st.markdown(
        """
        <style>
        /* サイドバー非表示 */
        section[data-testid="stSidebar"]              { display: none !important; }
        button[data-testid="stSidebarCollapseButton"]  { display: none !important; }
        [data-testid="collapsedControl"]               { display: none !important; }

        /* 両横余白・上下余白の縮小 / スクロール確保 */
        .block-container {
            padding-top: 0.8rem !important;
            padding-bottom: 3.5rem !important;  /* 固定ボトムバー(32px) + バッファ */
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 100% !important;
        }

        /* 見出しサイズ縮小 */
        h2 { font-size: 1.4rem !important; }
        h4 { font-size: 1.0rem !important; }
        h5 { font-size: 0.9rem !important; }

        /* 要素間の縦隙間を縮小 */
        div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] {
            gap: 0.3rem !important;
        }
        /* divider の余白を縮小 */
        hr { margin: 0.4rem 0 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _inject_status_bar(
    is_running: bool,
    monitored_count: int,
    total_count: int,
) -> None:
    """
    画面下部に固定ステータスバーを JS で注入する。
    MutationObserver により Streamlit の再レンダリング後も生存する。
    状態が変わるたびに innerHTML / background を更新する。
    """
    status_icon = "🟢 スキャン中" if is_running else "⚪ 停止中"
    bar_color   = "#1a472a"       if is_running else "#2c2c2c"
    bar_text = (
        f"{status_icon} &nbsp;|&nbsp; "
        f"間隔: {config.SCAN_INTERVAL_MINUTES}分 &nbsp;|&nbsp; "
        f"取引時間: {config.TRADING_START_TIME}〜{config.TRADING_END_TIME} &nbsp;|&nbsp; "
        f"監視: {monitored_count} / {total_count} 件"
    )

    components.html(
        f"""
        <script>
        (function () {{
            var TEXT  = '{bar_text}';
            var COLOR = '{bar_color}';

            function ensureBar() {{
                var doc = window.parent.document;
                var bar = doc.getElementById('surge-status-bar');
                if (!bar) {{
                    bar = doc.createElement('div');
                    bar.id = 'surge-status-bar';
                    bar.style.cssText = [
                        'position:fixed', 'bottom:0', 'left:0', 'right:0',
                        'height:32px', 'color:#eeeeee', 'font-size:13px',
                        'display:flex', 'align-items:center', 'padding:0 16px',
                        'z-index:9999', 'font-family:sans-serif'
                    ].join(';');
                    doc.body.appendChild(bar);
                }}
                // 毎回テキストと背景色を更新
                bar.innerHTML = TEXT;
                bar.style.background = COLOR;
            }}

            ensureBar();
            var obs = new MutationObserver(ensureBar);
            obs.observe(window.parent.document.body, {{ childList: true, subtree: false }});
        }})();
        </script>
        """,
        height=0,
    )


# ----------------------------------------------------------------
# コンパクトスキャナーコントロール（タブ上部）
# ----------------------------------------------------------------

def _render_scanner_controls_compact() -> None:
    """タブ上部にコンパクトなスキャナーコントロールを横並びで表示する。"""
    scanner: SurgeScanner | None = st.session_state.get("scanner")
    is_running: bool = st.session_state.get("scanner_running", False)

    col_btn, col_status, _col_spacer = st.columns([1, 1.2, 6])

    with col_btn:
        if scanner is None:
            st.button("スキャナーエラー", disabled=True, key="scanner_err",
                      use_container_width=True)
        elif is_running:
            if st.button("⏹ 停止", type="secondary", key="scanner_stop",
                         use_container_width=True):
                try:
                    scanner.stop()
                    st.session_state.scanner_running = False
                    logger.info("SurgeScanner を停止しました。")
                except Exception as e:
                    logger.error(f"SurgeScanner の停止に失敗: {e}", exc_info=True)
                    st.error("スキャナーの停止に失敗しました。")
                st.rerun()
        else:
            if st.button("▶ 開始", type="primary", key="scanner_start",
                         use_container_width=True):
                try:
                    scanner.start()
                    st.session_state.scanner_running = True
                    logger.info("SurgeScanner を開始しました。")
                except Exception as e:
                    logger.error(f"SurgeScanner の開始に失敗: {e}", exc_info=True)
                    st.error("スキャナーの開始に失敗しました。")
                st.rerun()

    with col_status:
        bg    = "#1a472a" if is_running else "#2c2c2c"
        label = "🟢 スキャン中" if is_running else "⚪ 停止中"
        st.markdown(
            f'<div style="display:inline-flex;align-items:center;height:38px;'
            f'padding:0 14px;border-radius:6px;background:{bg};'
            f'color:#eeeeee;font-size:14px;white-space:nowrap;width:fit-content">{label}</div>',
            unsafe_allow_html=True,
        )


# ----------------------------------------------------------------
# スキャン結果表示
# ----------------------------------------------------------------

def _render_surge_results(results: list[SurgeResult]) -> None:
    """急騰スキャン結果をカード形式で表示する。"""
    if not results:
        st.info("急騰銘柄は見つかりませんでした。")
        return

    st.markdown(f"#### 🚨 急騰検知: {len(results)} 銘柄")
    for r in results:
        with st.container(border=True):
            st.markdown(f"##### 【急騰】{r.ticker}")

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

    # --- CSS/JS インジェクション ---
    _inject_cancel_label()
    _inject_sidebar_hide()

    # --- フェッチャー・スキャナー初期化 ---
    fetcher = get_fetcher()
    _init_scanner()

    # --- ステータスバー用件数を取得（watchlist_settings は初期化済み前提） ---
    settings_map: dict = st.session_state.get("watchlist_settings", {})
    total_count     = len(settings_map)
    monitored_count = sum(1 for s in settings_map.values() if s.get("enabled", True))
    is_running      = st.session_state.get("scanner_running", False)

    # --- 固定ボトムバー注入 ---
    _inject_status_bar(is_running, monitored_count, total_count)

    # --- ページタイトル ---
    st.markdown("## 📈 株価監視・急騰通知アプリ")

    # --- コンパクトスキャナーコントロール ---
    _render_scanner_controls_compact()

    st.divider()

    # --- タブ構成 ---
    tabs = st.tabs(["👀 監視銘柄管理"])

    with tabs[0]:
        watchlist = render_watchlist()

        # スキャナーのウォッチリストを最新状態に同期（enabled=True のみ）
        scanner: SurgeScanner | None = st.session_state.get("scanner")
        if scanner is not None:
            scanner.update_watchlist(watchlist)

        st.divider()

        # --- 手動スキャン ---
        st.markdown("#### 🔍 今すぐスキャン")
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
