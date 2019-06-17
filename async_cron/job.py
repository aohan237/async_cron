import arrow
import inspect
import functools
import asyncio
import uuid
from dateutil import tz
import datetime
from .units import SECOND, MINUTE, HOUR, DAY, MONTH, WEEK
import logging

logger = logging.getLogger(__package__)


class CronJob:
    """
    periodic job
    """

    def __init__(self, name: str = None, interval: int = 1, scheduler=None,
                 loop=None, tz: str = None, run_total: int = None,
                 tolerance: int = 10):
        """
        :param name: crontab name
        :param interval: crontab apply interval
        :param scheduler: crontab scheduler instance for now ,it is useless
        :param loop: asyncio running loop
        :param tz: timezone info. support string tz format
        :param run_total: crontab task total running times,
        :       with this parameter,you can limit its cron task count
        :param tolerance: crontab tolerance. time tolerance, within is range,
        :       task will still be applied
        """
        self.name = name or str(uuid.uuid1())
        self.interval = interval
        self.job_func = None
        self.unit = None
        self.at_time = (None, None)
        self.at_exact_time = None
        self.last_run = None
        self.next_run = None
        self.run_count = 0
        self.run_total = run_total
        self.period = None
        self.week_day = None
        self.month_day = None
        self.scheduler = scheduler
        self.loop = loop or asyncio.get_event_loop()
        self.gte_day = False
        self.tz = tz
        # tolerance means if now - at_exact_time <= tolerance,
        # this job will still be applied
        self.tolerance = datetime.timedelta(
            seconds=tolerance)

    def __repr__(self):
        return f"{self.name}-{self.interval}:{self.unit}-{self.at_time}\
            -{self.at_exact_time}-{self.run_total}"

    def __eq__(self, job=None):
        if (self.interval == job.interval and
                self.unit == job.unit and
                self.at_time == job.at_time and
                self.run_total == job.run_total and
                self.at_exact_time == job.at_exact_time):
            return True
        else:
            return False

    def check_gte_day(self):
        if self.unit in (SECOND, MINUTE, HOUR):
            self.gte_day = False
        else:
            self.gte_day = True

    def get_now(self):
        now = arrow.utcnow()
        if self.tz:
            now = now.to(self.tz)
        else:
            now = now.to(tz.tzlocal())
        return now

    def get_tz_time(self, arw=None):
        if self.tz:
            arw = arw.to(self.tz)
        else:
            arw = arw.to(tz.tzlocal())
        return arw

    def decide_run(self):
        now = self.get_now()
        if self.at_exact_time:
            # check if it is a exact run func
            if (now >= self.at_exact_time and
                    now - self.at_exact_time <= self.tolerance):
                return True
            else:
                return False

        if self.next_run:
            if now >= self.next_run:
                return True
        else:
            if self.month_day and self.month_day != now.day:
                return False
            if self.week_day and self.week_day != now.weekday():
                return False
            now_datetime = now.datetime
            hour, minute = self.at_time
            if hour is not None and minute is not None:
                if (now_datetime.hour == hour and
                        now_datetime.minute == minute):
                    return True
            elif hour is not None:
                if now_datetime.hour == hour:
                    return True
            elif minute is not None:
                if now_datetime.minute == minute:
                    print(now_datetime.minute, minute)
                    return True
            else:
                return True
        return False

    def remove(self):
        if self.run_total:
            if self.run_count >= self.run_total:
                return True
        return False

    def go(self, job_func, *args, **kwargs):
        self.job_func = functools.partial(job_func, *args, **kwargs)
        return self

    def run(self):
        if self.job_func is None:
            return
        now = self.get_now()
        # recodrd run args
        self.last_run = now
        self.run_count += 1
        # run job_func
        tmp_result = self.job_func()
        if inspect.iscoroutine(tmp_result):
            self.loop.create_task(tmp_result)
        self.gen_next_run()
        return tmp_result

    def gen_next_run(self):
        if not self.at_exact_time:
            self.next_run = self.last_run.shift(**{self.unit: self.interval})

    def split_time(self, time_string: str = None):
        hour, minute = time_string.split(':')
        hour = int(hour) if hour else None
        minute = int(minute) if minute else None
        return (hour, minute)

    def at(self, time_string: str = None, time_shift=8):
        if time_string is None:
            pass
        else:
            time_string = time_string.replace('：', ':')
            first, *_ = time_string.split(':')
            if len(first) > 2:
                try:
                    arrow_time = arrow.get(time_string)
                    arrow_time = self.get_tz_time(
                        arrow_time).shift(hours=-time_shift)
                    self.at_exact_time = arrow_time
                    self.run_total = 1
                except Exception as tmp:
                    logger.exception(tmp)
                    logger.info(f'{self.name} parse datetime error')
            else:
                try:
                    self.at_time = self.split_time(time_string)
                except Exception as tmp:
                    logger.exception(tmp)
                    logger.info(f'{self.name} parse hour and minute error')
        return self

    def every(self, interval: int = None):
        if interval is None:
            pass
        else:
            self.interval = interval
        return self

    @property
    def second(self):
        self.unit = SECOND
        self.check_gte_day()
        return self

    @property
    def minute(self):
        self.unit = MINUTE
        self.check_gte_day()
        return self

    @property
    def hour(self):
        self.unit = HOUR
        self.check_gte_day()
        return self

    @property
    def day(self):
        self.unit = DAY
        return self

    @property
    def week(self):
        self.unit = WEEK
        return self

    def weekday(self, week_day: int = None):
        self.unit = WEEK
        self.week_day = week_day
        return self

    def monthday(self, month_day: int = None):
        self.unit = MONTH
        self.month_day = month_day
        return self

    @property
    def month(self):
        self.unit = MONTH
        return self
