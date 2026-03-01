# ui/utils.py
import logging

import streamlit as st
import yfinance as yf

logger = logging.getLogger(__name__)


@st.cache_data(ttl=3600, show_spinner=False)
def get_company_name(ticker: str) -> str:
    """
    銘柄コードから会社名を取得する（yfinance 経由、1時間キャッシュ）。

    Args:
        ticker: 4桁の日本株コード（例: "7203"）。
    Returns:
        会社名文字列。取得失敗時は ticker をそのまま返す。
    """
    try:
        yf_ticker = f"{ticker}.T" if ticker.isdigit() else ticker
        info = yf.Ticker(yf_ticker).info
        name = info.get("longName") or info.get("shortName") or ticker
        return name
    except Exception as e:
        logger.warning(f"会社名の取得に失敗しました ({ticker}): {e}")
        return ticker
