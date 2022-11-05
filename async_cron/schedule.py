import asyncio
from .job import CronJob
import logging

logger = logging.getLogger(__package__)


class Scheduler:
    def __init__(self, name=None, check_interval: int = 1,
                 loop=None, debug=False, locale=None):
        """
        :param name:name of the scheduler
        :param check_interval: check interval of the scheduler, unit is second
        :param locale: locale for humanized time,follows the general rule of locale
        """
        self.name = name
        self.check_interval = check_interval
        self.loop = loop or asyncio.get_event_loop()
        self.jobs = {}
        self.locale = locale or "en_US"
        if not debug:
            logger.setLevel(logging.ERROR)

    async def start(self):
        while True:
            try:
                await self.check_jobs()
                await asyncio.sleep(self.check_interval)
            except KeyboardInterrupt:
                logger.debug('keyboard interrupt,exit')
                break
            except Exception as tmp:
                logger.exception(tmp)
                logger.debug('error occurs,exit')
                break

    def add_job(self, job: CronJob = None):
        if job.name in self.jobs:
            if self.jobs[job.name] == job:
                pass
        else:
            self.jobs[job.name] = job

    def del_job(self, job_name: str = None):
        if job_name in self.jobs:
            del self.jobs[job_name]
        else:
            logger.debug('{} is in scheduler jobs list'.format(job_name))

    async def check_jobs(self):
        remove_list = []
        for name, job in self.jobs.items():
            if job.decide_run():
                now = job.get_now()
                logger.debug('running:{}:{}'.format(job.name, now.humanize(locale=self.locale)))
                job.run()
                if job.remove():
                    remove_list.append(name)
        for i in remove_list:
            self.del_job(i)
            logger.debug('{} is out of date, remove job'.format(i))
