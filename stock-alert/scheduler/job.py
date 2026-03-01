# scheduler/job.py
import datetime
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

import config
from analysis.detector import SurgeResult, scan_watchlist
from data.base_fetcher import BaseFetcher
from data.yfinance_fetcher import YfinanceFetcher
from notification.line_notifier import LineNotifier, create_notifier_from_config

# ロガー設定（ライブラリモジュールのため basicConfig は呼ばない）
logger = logging.getLogger(__name__)

_JST = ZoneInfo("Asia/Tokyo")


# ----------------------------------------------------------------
# NullNotifier: LINE 未設定時のフォールバック
# ----------------------------------------------------------------

class NullNotifier:
    """
    LINE 設定がない場合に LineNotifier の代わりに使うダミー通知クラス。
    実際には何も送信せず、常に 0 を返す。
    """

    def send_surge_alerts(self, results: list[SurgeResult]) -> int:
        logger.info("LINE 通知は未設定のため、通知をスキップします。")
        return 0


# ----------------------------------------------------------------
# SurgeScanner: メインスキャナークラス
# ----------------------------------------------------------------

class SurgeScanner:
    """
    APScheduler を使って場中スキャンを定期実行するスケジューラ。

    指定された間隔でウォッチリストをスキャンし、
    急騰銘柄を検知した場合は LINE に通知する。
    """

    def __init__(
        self,
        watchlist: list[dict],
        fetcher: BaseFetcher,
        notifier: LineNotifier | NullNotifier,
        interval_minutes: int = config.SCAN_INTERVAL_MINUTES,
        start_time: str = config.TRADING_START_TIME,
        end_time: str = config.TRADING_END_TIME,
    ) -> None:
        """
        Args:
            watchlist:        監視銘柄リスト（render_watchlist() の戻り値形式）
            fetcher:          OHLCVデータ取得器
            notifier:         LINE 通知クラス（または NullNotifier）
            interval_minutes: スキャン間隔（分）
            start_time:       取引開始時刻（"HH:MM" 形式）
            end_time:         取引終了時刻（"HH:MM" 形式）
        """
        self.watchlist        = watchlist
        self.fetcher          = fetcher
        self.notifier         = notifier
        self.interval_minutes = interval_minutes
        self.start_time       = start_time
        self.end_time         = end_time

        # BackgroundScheduler を東京タイムゾーンで初期化
        self._scheduler = BackgroundScheduler(timezone="Asia/Tokyo")

    # ----------------------------------------------------------------
    # パブリックメソッド
    # ----------------------------------------------------------------

    def start(self) -> None:
        """
        スケジューラを開始し、スキャンジョブを登録する。
        取引時間外でも起動でき、ジョブ内で時間外判定を行う。
        """
        self._scheduler.add_job(
            self._scan_job,
            IntervalTrigger(minutes=self.interval_minutes),
            id="surge_scan",
            name="急騰銘柄スキャン",
            max_instances=1,          # 前回ジョブ実行中の二重起動を防止
            replace_existing=True,    # 同 id のジョブがあれば置き換え
        )
        self._scheduler.start()
        logger.info(
            f"スキャンスケジューラを開始しました。"
            f"間隔={self.interval_minutes}分 / "
            f"取引時間={self.start_time}〜{self.end_time}"
        )

    def stop(self) -> None:
        """スケジューラを停止する（実行中ジョブの完了は待たない）。"""
        self._scheduler.shutdown(wait=False)
        logger.info("スキャンスケジューラを停止しました。")

    def update_watchlist(self, watchlist: list[dict]) -> None:
        """
        実行中のスケジューラのウォッチリストを動的に差し替える。

        Args:
            watchlist: 新しいウォッチリスト（render_watchlist() の戻り値形式）
        """
        self.watchlist = watchlist
        logger.info(f"ウォッチリストを更新しました。銘柄数={len(self.watchlist)}")

    # ----------------------------------------------------------------
    # プライベートメソッド
    # ----------------------------------------------------------------

    def _parse_time(self, time_str: str) -> datetime.time:
        """
        "HH:MM" 形式の文字列を datetime.time に変換する。

        Raises:
            ValueError: 形式が不正な場合
        """
        h, m = map(int, time_str.split(":"))
        return datetime.time(h, m)

    def _is_trading_hours(self, now: datetime.datetime) -> bool:
        """
        現在時刻が取引時間内かどうかを判定する。

        Args:
            now: Asia/Tokyo タイムゾーンの現在時刻

        Returns:
            取引時間内なら True
        """
        try:
            start = self._parse_time(self.start_time)
            end   = self._parse_time(self.end_time)
        except ValueError:
            logger.error(
                f"取引時間のパースに失敗しました: "
                f"start='{self.start_time}' end='{self.end_time}'"
            )
            return False

        return start <= now.time() <= end

    def _scan_job(self) -> None:
        """
        APScheduler から定期的に呼び出されるスキャンジョブ。

        取引時間外はスキップ。取引時間内であればスキャン・通知を実行する。
        例外はキャッチしてログ出力し、スケジューラを継続させる。
        """
        now = datetime.datetime.now(_JST)

        # 取引時間外はスキップ
        if not self._is_trading_hours(now):
            logger.debug(
                f"取引時間外 ({now.strftime('%H:%M')}) のためスキャンをスキップします。"
            )
            return

        logger.info(f"スキャン開始 ({now.strftime('%H:%M')}) / 銘柄数={len(self.watchlist)}")

        try:
            results: list[SurgeResult] = scan_watchlist(self.watchlist, self.fetcher)

            surge_count = len(results)
            if surge_count > 0:
                sent = self.notifier.send_surge_alerts(results)
                logger.info(
                    f"スキャン完了: 急騰検知={surge_count}件 / LINE通知={sent}件"
                )
            else:
                logger.info(
                    f"スキャン完了: 急騰検知なし（{len(self.watchlist)}銘柄をスキャン）"
                )

        except Exception as e:
            # 例外が発生してもスケジューラを止めない
            logger.error(f"スキャンジョブ中にエラーが発生しました: {e}", exc_info=True)


# ----------------------------------------------------------------
# ファクトリ関数
# ----------------------------------------------------------------

def create_scanner_from_config(watchlist: list[dict]) -> SurgeScanner:
    """
    config.py の設定値から SurgeScanner を生成して返す。

    LINE 未設定（ValueError）の場合は NullNotifier を使う。

    Args:
        watchlist: 監視銘柄リスト（render_watchlist() の戻り値形式）

    Returns:
        SurgeScanner インスタンス
    """
    fetcher: BaseFetcher = YfinanceFetcher()

    notifier: LineNotifier | NullNotifier
    try:
        notifier = create_notifier_from_config()
        logger.info("LineNotifier を設定しました。")
    except ValueError as e:
        logger.warning(f"LINE 通知を無効化します（未設定）: {e}")
        notifier = NullNotifier()

    return SurgeScanner(
        watchlist=watchlist,
        fetcher=fetcher,
        notifier=notifier,
        interval_minutes=config.SCAN_INTERVAL_MINUTES,
        start_time=config.TRADING_START_TIME,
        end_time=config.TRADING_END_TIME,
    )
