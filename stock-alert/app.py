# app.py
import sys
import os

import streamlit as st

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(__file__))

import config
from data.base_fetcher import BaseFetcher
from data.yfinance_fetcher import YfinanceFetcher
from ui.chart import render_chart
from ui.watchlist import render_watchlist


def get_fetcher() -> BaseFetcher:
    """
    config.DATA_SOURCEに応じたデータ取得インスタンスを返す。
    将来的にauカブコム証券APIに対応する場合はここに追加する。
    """
    if config.DATA_SOURCE == "yfinance":
        return YfinanceFetcher()
    else:
        # auカブコム証券API対応後に実装
        raise NotImplementedError(f"未対応のデータソース: {config.DATA_SOURCE}")


def main() -> None:
    """Streamlitアプリのエントリーポイント。"""

    st.set_page_config(
        page_title="株価監視・急騰通知アプリ",
        page_icon="📈",
        layout="wide",
    )

    # --- サイドバー ---
    with st.sidebar:
        st.title("📈 株価監視アプリ")
        st.divider()

        # ページ選択
        page = st.radio(
            "ページ選択",
            ["📊 チャート分析", "👀 監視銘柄管理"],
            label_visibility="collapsed",
        )

        st.divider()

        # データソース表示
        source_label = {
            "yfinance": "yfinance（15分遅延）",
            "kabucom":  "auカブコム証券API",
        }.get(config.DATA_SOURCE, config.DATA_SOURCE)

        st.caption(f"📡 データソース: **{source_label}**")

    # --- データ取得インスタンスを生成 ---
    fetcher = get_fetcher()

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


if __name__ == "__main__":
    main()
