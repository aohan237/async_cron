import asyncio
from .job import CronJob
from .logger import get_logger


class Scheduler:
    def __init__(self, name=None, check_interval: int=5,
                 loop=None, log_level=None):
        """
        @param name:name of the scheduler
        @param check_interval: check interval of the scheduler, unit is second
        """
        self.name = name
        self.check_interval = check_interval
        self.loop = loop or asyncio.get_event_loop()
        self.jobs = {}
        self.logger = get_logger(log_level=log_level)

    async def start(self):
        while True:
            try:
                await self.check_jobs()
                await asyncio.sleep(self.check_interval)
            except Exception as tmp:
                self.logger.exception(tmp)
                self.logger.info('error occurs,exit')
                break

    def add_job(self, job: CronJob=None):
        self.jobs[job.name] = job

    def del_job(self, job_name: str=None):
        if job_name in self.jobs:
            del self.jobs[job_name]
        else:
            self.logger.info(f'{job_name} is in scheduler jobs list')

    async def check_jobs(self):
        remove_list = []
        for name, job in self.jobs.items():
            if job.decide_run():
                now = job.get_now()
                self.logger.info(
                    f'runing:{job.name}:{now.humanize(locale="zh_CN")}')
                job.run()
                if job.remove():
                    remove_list.append(name)
        for i in remove_list:
            self.del_job(i)
            self.logger.info(f'{i} is out of date ,delete')
