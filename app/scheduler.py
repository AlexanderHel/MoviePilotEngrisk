import logging
from datetime import datetime, timedelta
from typing import List

import pytz
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler

from app import schemas
from app.chain import ChainBase
from app.chain.cookiecloud import CookieCloudChain
from app.chain.mediaserver import MediaServerChain
from app.chain.subscribe import SubscribeChain
from app.chain.tmdb import TmdbChain
from app.chain.transfer import TransferChain
from app.core.config import settings
from app.db import SessionFactory
from app.log import logger
from app.utils.singleton import Singleton
from app.utils.timer import TimerUtils

#  Gain apscheduler  The logger of the
scheduler_logger = logging.getLogger('apscheduler')

#  Set the log level to WARNING
scheduler_logger.setLevel(logging.WARNING)


class SchedulerChain(ChainBase):
    pass


class Scheduler(metaclass=Singleton):
    """
    Scheduled task management
    """
    #  Time service
    _scheduler = BackgroundScheduler(timezone=settings.TZ,
                                     executors={
                                         'default': ThreadPoolExecutor(20)
                                     })

    def __init__(self):
        #  Database connection
        self._db = SessionFactory()
        #  Operational status of each service
        self._jobs = {
            "cookiecloud": {
                "func": CookieCloudChain(self._db).process,
                "running": False,
            },
            "mediaserver_sync": {
                "func": MediaServerChain(self._db).sync,
                "running": False,
            },
            "subscribe_tmdb": {
                "func": SubscribeChain(self._db).check,
                "running": False,
            },
            "subscribe_search": {
                "func": SubscribeChain(self._db).search,
                "running": False,
            },
            "subscribe_refresh": {
                "func": SubscribeChain(self._db).refresh,
                "running": False,
            },
            "transfer": {
                "func": TransferChain(self._db).process,
                "running": False,
            }
        }

        #  Debug mode does not start the timing service
        if settings.DEV:
            return

        # CookieCloud Timing synchronization
        if settings.COOKIECLOUD_INTERVAL:
            self._scheduler.add_job(
                self.start,
                "interval",
                id="cookiecloud",
                name=" SynchronizationCookieCloud Website",
                minutes=settings.COOKIECLOUD_INTERVAL,
                next_run_time=datetime.now(pytz.timezone(settings.TZ)) + timedelta(minutes=1),
                kwargs={
                    'job_id': 'cookiecloud'
                }
            )

        #  Media server synchronization
        if settings.MEDIASERVER_SYNC_INTERVAL:
            self._scheduler.add_job(
                self.start,
                "interval",
                id="mediaserver_sync",
                name=" Synchronous media server",
                hours=settings.MEDIASERVER_SYNC_INTERVAL,
                next_run_time=datetime.now(pytz.timezone(settings.TZ)) + timedelta(minutes=5),
                kwargs={
                    'job_id': 'mediaserver_sync'
                }
            )

        #  Add search on subscription（5 Check every minute.）
        self._scheduler.add_job(
            self.start,
            "interval",
            minutes=5,
            kwargs={
                'job_id': 'subscribe_search',
                'state': 'N'
            }
        )

        #  Check for updated subscriptionsTMDB Digital（ At intervals of6 Hourly）
        self._scheduler.add_job(
            self.start,
            "interval",
            id="subscribe_tmdb",
            name=" Subscribe to metadata updates",
            hours=6,
            kwargs={
                'job_id': 'subscribe_tmdb'
            }
        )

        #  The subscription status is set every24 Hourly searches
        if settings.SUBSCRIBE_SEARCH:
            self._scheduler.add_job(
                self.start,
                "interval",
                id="subscribe_search",
                name=" Subscribe to search",
                hours=24,
                kwargs={
                    'job_id': 'subscribe_search',
                    'state': 'R'
                }
            )

        if settings.SUBSCRIBE_MODE == "spider":
            #  Site home seed timed refresh mode
            triggers = TimerUtils.random_scheduler(num_executions=30)
            for trigger in triggers:
                self._scheduler.add_job(
                    self.start,
                    "cron",
                    id=f"subscribe_refresh|{trigger.hour}:{trigger.minute}",
                    name=" Subscription refresh",
                    hour=trigger.hour,
                    minute=trigger.minute,
                    kwargs={
                        'job_id': 'subscribe_refresh'
                    })
        else:
            # RSS Subscription model
            if not settings.SUBSCRIBE_RSS_INTERVAL:
                settings.SUBSCRIBE_RSS_INTERVAL = 30
            elif settings.SUBSCRIBE_RSS_INTERVAL < 5:
                settings.SUBSCRIBE_RSS_INTERVAL = 5
            self._scheduler.add_job(
                self.start,
                "interval",
                id="subscribe_refresh",
                name="RSS Subscription refresh",
                minutes=settings.SUBSCRIBE_RSS_INTERVAL,
                kwargs={
                    'job_id': 'subscribe_refresh'
                }
            )

        #  Downloader file transfer（ Each5 Minutes）
        if settings.DOWNLOADER_MONITOR:
            self._scheduler.add_job(
                self.start,
                "interval",
                id="transfer",
                name=" Download file organization",
                minutes=5,
                kwargs={
                    'job_id': 'transfer'
                }
            )

        #  Backstage refreshTMDB Wallpapers
        self._scheduler.add_job(
            TmdbChain(self._db).get_random_wallpager,
            "interval",
            minutes=30,
            next_run_time=datetime.now(pytz.timezone(settings.TZ)) + timedelta(seconds=3)
        )

        #  Public timing service
        self._scheduler.add_job(
            SchedulerChain(self._db).scheduler_job,
            "interval",
            minutes=10
        )

        #  Printing service
        logger.debug(self._scheduler.print_jobs())

        #  Start timing service
        self._scheduler.start()

    def start(self, job_id: str, *args, **kwargs):
        """
        Start timing service
        """
        #  Deal withjob_id Specification
        job = self._jobs.get(job_id)
        if not job:
            return
        if job.get("running"):
            logger.warning(f" Timed task {job_id}  Running ...")
            return
        self._jobs[job_id]["running"] = True
        try:
            job["func"](*args, **kwargs)
        except Exception as e:
            logger.error(f" Timed task {job_id}  Failure of execution：{e}")
        self._jobs[job_id]["running"] = False

    def list(self) -> List[schemas.ScheduleInfo]:
        """
        All current tasks
        """
        #  Return to timing tasks
        schedulers = []
        #  De-emphasize
        added = []
        jobs = self._scheduler.get_jobs()
        #  Sort by next run time
        jobs.sort(key=lambda x: x.next_run_time)
        for job in jobs:
            if job.name not in added:
                added.append(job.name)
            else:
                continue
            job_id = job.id.split("|")[0]
            if not self._jobs.get(job_id):
                continue
            #  Mission status
            status = " Running" if self._jobs[job_id].get("running") else " Wait for"
            #  Next run time
            next_run = TimerUtils.time_difference(job.next_run_time)
            schedulers.append(schemas.ScheduleInfo(
                id=job_id,
                name=job.name,
                status=status,
                next_run=next_run
            ))
        return schedulers

    def stop(self):
        """
        Turning off the timing service
        """
        if self._scheduler.running:
            self._scheduler.shutdown()
        if self._db:
            self._db.close()
