# ui/utils.py
import logging

import streamlit as st
import yfinance as yf

logger = logging.getLogger(__name__)


@st.cache_data(ttl=3600, show_spinner=False)
def get_company_name(ticker: str) -> str:
    """
    ティッカーコードから銘柄名を取得する（1時間キャッシュ）。

    日本株（4桁数字）は自動的に ".T" を付与して yfinance に問い合わせる。
    取得失敗時はティッカーコードをそのまま返す。

    Args:
        ticker: 銘柄コード（例: "7203"）

    Returns:
        銘柄名（例: "Toyota Motor Corporation"）、取得失敗時は ticker をそのまま返す
    """
    try:
        yf_ticker = f"{ticker}.T" if ticker.isdigit() else ticker
        info = yf.Ticker(yf_ticker).info
        name = info.get("longName") or info.get("shortName") or ticker
        return name
    except Exception as e:
        logger.debug(f"銘柄名の取得に失敗しました ({ticker}): {e}")
        return ticker
