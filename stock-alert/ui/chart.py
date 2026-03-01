# ui/chart.py
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from data.base_fetcher import BaseFetcher, Timeframe
from analysis.indicators import add_technical_indicators
from ui.utils import get_company_name

# 15分未満の足種（yfinance制限対象）
LIMITED_TIMEFRAMES = {Timeframe.SECOND, Timeframe.MINUTE_1, Timeframe.MINUTE_5, Timeframe.MINUTE_10}

# 期間ラベル → yfinance period 文字列マッピング
PERIOD_MAP: dict[str, str] = {
    "1週間": "5d",
    "1ヶ月": "1mo",
    "3ヶ月": "3mo",
    "6ヶ月": "6mo",
    "1年":   "1y",
}


def render_chart(ticker: str, fetcher: BaseFetcher) -> None:
    """
    指定銘柄の株価チャートをStreamlit上にレンダリングする。

    Args:
        ticker: 銘柄コード（例: "7203"）
        fetcher: データ取得インスタンス
    """
    st.header(f"📊 {ticker}　{get_company_name(ticker)}")

    # --- Session State 初期化 ---
    if "chart_timeframe" not in st.session_state:
        st.session_state.chart_timeframe = Timeframe.DAY
    if "chart_period" not in st.session_state:
        st.session_state.chart_period = "1ヶ月"

    # --- サイドバー: 指標表示設定 ---
    with st.sidebar:
        st.subheader("📈 テクニカル指標")
        show_sma    = st.checkbox("SMA（移動平均線）",       value=True)
        show_ema    = st.checkbox("EMA（指数移動平均線）",   value=False)
        show_bb     = st.checkbox("ボリンジャーバンド",       value=True)
        show_rsi    = st.checkbox("RSI",                    value=True)
        show_macd   = st.checkbox("MACD",                   value=True)
        show_volume = st.checkbox("出来高",                  value=True)

    # --- 足種切り替えボタン ---
    st.subheader("足種選択")
    timeframes = list(Timeframe)
    cols = st.columns(len(timeframes))
    for i, tf in enumerate(timeframes):
        btn_type = "primary" if st.session_state.chart_timeframe == tf else "secondary"
        if cols[i].button(tf.label, key=f"tf_{tf.name}", type=btn_type):
            st.session_state.chart_timeframe = tf
            st.rerun()

    selected_tf = st.session_state.chart_timeframe

    # --- データソース制限の注記 ---
    if fetcher.is_timeframe_limited and selected_tf in LIMITED_TIMEFRAMES:
        st.warning("⚠️ データソースの制限により15分足で表示しています。")

    # --- 期間選択 ---
    period_label = st.selectbox(
        "表示期間",
        list(PERIOD_MAP.keys()),
        index=list(PERIOD_MAP.keys()).index(st.session_state.chart_period),
    )
    st.session_state.chart_period = period_label
    period = PERIOD_MAP[period_label]

    # --- データ取得 ---
    with st.spinner("データを取得中..."):
        df = fetcher.get_ohlcv(ticker, selected_tf, period)

    if df.empty:
        st.error("データを取得できませんでした。銘柄コードと期間を確認してください。")
        return

    # --- テクニカル指標計算 ---
    df = add_technical_indicators(df)

    # --- サブプロット構成を動的に決定 ---
    subplot_rows: list[str] = ["main"]  # メインチャートは常に表示
    if show_rsi:    subplot_rows.append("rsi")
    if show_macd:   subplot_rows.append("macd")
    if show_volume: subplot_rows.append("volume")

    n_rows = len(subplot_rows)
    row_heights = [0.55] + [0.15] * (n_rows - 1) if n_rows > 1 else [1.0]

    subplot_titles = [f"{ticker} ローソク足"] + [
        {"rsi": "RSI", "macd": "MACD", "volume": "出来高"}[r]
        for r in subplot_rows[1:]
    ]

    fig = make_subplots(
        rows=n_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=subplot_titles,
    )

    # --- 1段目: ローソク足 ---
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=df["Close"],
        name="ローソク足",
        increasing_line_color="red",    # 陽線: 赤
        decreasing_line_color="#00aa00",  # 陰線: 緑
    ), row=1, col=1)

    # SMA
    if show_sma:
        for length, color in [(5, "orange"), (25, "purple"), (75, "gray")]:
            col_name = f"SMA_{length}"
            if col_name in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index, y=df[col_name],
                    mode="lines", name=f"SMA {length}",
                    line=dict(color=color, width=1),
                ), row=1, col=1)

    # EMA
    if show_ema:
        for length, color in [(5, "cyan"), (25, "magenta")]:
            col_name = f"EMA_{length}"
            if col_name in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index, y=df[col_name],
                    mode="lines", name=f"EMA {length}",
                    line=dict(color=color, width=1, dash="dot"),
                ), row=1, col=1)

    # ボリンジャーバンド
    if show_bb and "BB_UPPER" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_UPPER"],
            mode="lines", name="BB +2σ",
            line=dict(color="royalblue", width=1, dash="dash"),
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_MIDDLE"],
            mode="lines", name="BB 中央",
            line=dict(color="royalblue", width=1),
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["BB_LOWER"],
            mode="lines", name="BB -2σ",
            line=dict(color="royalblue", width=1, dash="dash"),
            fill="tonexty", fillcolor="rgba(65,105,225,0.05)",
        ), row=1, col=1)

    # --- RSI ---
    if show_rsi and "RSI_14" in df.columns:
        rsi_row = subplot_rows.index("rsi") + 1
        fig.add_trace(go.Scatter(
            x=df.index, y=df["RSI_14"],
            mode="lines", name="RSI 14",
            line=dict(color="limegreen"),
        ), row=rsi_row, col=1)
        # 過熱・売られ過ぎのライン
        for level, color in [(70, "red"), (30, "blue")]:
            fig.add_hline(y=level, line_dash="dash", line_color=color,
                          line_width=1, row=rsi_row, col=1)
        fig.update_yaxes(range=[0, 100], row=rsi_row, col=1)

    # --- MACD ---
    if show_macd and "MACD" in df.columns:
        macd_row = subplot_rows.index("macd") + 1
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MACD"],
            mode="lines", name="MACD",
            line=dict(color="dodgerblue"),
        ), row=macd_row, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MACD_SIGNAL"],
            mode="lines", name="シグナル",
            line=dict(color="orange"),
        ), row=macd_row, col=1)
        hist_colors = ["red" if v >= 0 else "#00aa00" for v in df["MACD_HIST"]]
        fig.add_trace(go.Bar(
            x=df.index, y=df["MACD_HIST"],
            name="ヒストグラム",
            marker_color=hist_colors,
        ), row=macd_row, col=1)

    # --- 出来高 ---
    if show_volume and "Volume" in df.columns:
        vol_row = subplot_rows.index("volume") + 1
        vol_colors = [
            "red" if df["Close"].iloc[i] >= df["Open"].iloc[i] else "#00aa00"
            for i in range(len(df))
        ]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"],
            name="出来高",
            marker_color=vol_colors,
        ), row=vol_row, col=1)
        if "VOLUME_SMA_20" in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["VOLUME_SMA_20"],
                mode="lines", name="出来高SMA 20",
                line=dict(color="purple", width=1),
            ), row=vol_row, col=1)
        # Y軸を整数カンマ区切りで明示（省略表記の文字化け防止）
        fig.update_yaxes(tickformat=",.0f", row=vol_row, col=1)

    # --- レイアウト設定 ---
    fig.update_layout(
        height=800,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
        margin=dict(l=40, r=40, t=60, b=40),
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.2)")

    st.plotly_chart(fig, use_container_width=True)
