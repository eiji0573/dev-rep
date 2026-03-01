# notification/line_notifier.py
import logging

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    TextMessage,
)

import config
from analysis.detector import SurgeResult

# ロガー設定（ライブラリモジュールのため basicConfig は呼ばない）
logger = logging.getLogger(__name__)


class LineNotifier:
    """LINE Messaging API を使って急騰アラートを Push 送信するクラス。"""

    def __init__(self, token: str, user_id: str) -> None:
        """
        Args:
            token:   LINE Channel Access Token
            user_id: 通知先の LINE User ID

        Raises:
            ValueError: token または user_id が空文字の場合
        """
        if not token:
            raise ValueError("LINE_CHANNEL_ACCESS_TOKEN が設定されていません。")
        if not user_id:
            raise ValueError("LINE_USER_ID が設定されていません。")

        self.user_id = user_id

        # LINE Messaging API クライアントを初期化
        configuration = Configuration(access_token=token)
        self._api_client = ApiClient(configuration)
        self._messaging_api = MessagingApi(self._api_client)

        logger.info("LineNotifier を初期化しました。")

    # ----------------------------------------------------------------
    # プライベートメソッド
    # ----------------------------------------------------------------

    def _format_message(self, result: SurgeResult) -> str:
        """SurgeResult を LINE 送信用テキストに変換する。"""
        gc_label = "あり" if result.golden_cross else "なし"
        bb_label = "あり" if result.bb_breakout else "なし"

        return (
            f"【急騰アラート】{result.ticker}\n"
            f"終値: {result.latest_close:,.0f}円\n"
            f"前日終値比: {result.price_change_prev_close:+.2f}%\n"
            f"始値比: {result.price_change_open:+.2f}%\n"
            f"出来高比: {result.volume_ratio:.1f}倍\n"
            f"RSI: {result.rsi:.1f}\n"
            f"GC: {gc_label}\n"
            f"BB上抜け: {bb_label}\n"
            f"検知時刻: {result.timestamp}"
        )

    # ----------------------------------------------------------------
    # パブリックメソッド
    # ----------------------------------------------------------------

    def send_surge_alert(self, result: SurgeResult) -> bool:
        """
        単一の急騰アラートを LINE に Push 送信する。

        Args:
            result: 急騰検知結果（SurgeResult）

        Returns:
            送信成功なら True、失敗なら False
        """
        try:
            message_text = self._format_message(result)
            request = PushMessageRequest(
                to=self.user_id,
                messages=[TextMessage(text=message_text)],
            )
            self._messaging_api.push_message(request)
            logger.info(f"LINE 通知を送信しました: {result.ticker}")
            return True

        except Exception as e:
            # LINE API エラー・ネットワークエラーいずれもログに記録してスキップ
            logger.error(f"LINE 通知の送信に失敗しました [{result.ticker}]: {e}")
            return False

    def send_surge_alerts(self, results: list[SurgeResult]) -> int:
        """
        複数の急騰アラートを 1 件ずつ送信する。

        Args:
            results: SurgeResult のリスト（空リストの場合は即座に 0 を返す）

        Returns:
            送信成功件数
        """
        if not results:
            logger.info("送信対象の急騰銘柄がありません。")
            return 0

        success_count = sum(
            1 for result in results if self.send_surge_alert(result)
        )
        logger.info(
            f"LINE 通知完了: {success_count}/{len(results)} 件成功"
        )
        return success_count


# ----------------------------------------------------------------
# ファクトリ関数
# ----------------------------------------------------------------

def create_notifier_from_config() -> LineNotifier:
    """
    config.py の設定値から LineNotifier を生成して返す。

    Raises:
        ValueError: LINE_CHANNEL_ACCESS_TOKEN または LINE_USER_ID が未設定の場合

    Returns:
        LineNotifier インスタンス
    """
    token   = config.LINE_CHANNEL_ACCESS_TOKEN
    user_id = config.LINE_USER_ID

    if not token:
        raise ValueError(
            "config.LINE_CHANNEL_ACCESS_TOKEN が空です。"
            ".env に LINE_CHANNEL_ACCESS_TOKEN を設定してください。"
        )
    if not user_id:
        raise ValueError(
            "config.LINE_USER_ID が空です。"
            ".env に LINE_USER_ID を設定してください。"
        )

    return LineNotifier(token, user_id)
