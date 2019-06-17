from .job import CronJob
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import asyncio
import subprocess
import logging

logger = logging.getLogger(__package__)


class JobLoader:
    def __init__(self, name=None, loop=None,
                 log_path=None, log_level=None, thread=True, **kwargs):
        self.name = name
        if thread:
            self.executor = ThreadPoolExecutor()
        else:
            self.executor = ProcessPoolExecutor()
        self.loop = loop or asyncio.get_event_loop()
        self.log_path = log_path.strip('/')

    async def load(self):
        raise NotImplementedError

    @staticmethod
    def sub_process_command(command, env, name, log_path):
        out_path_name = log_path + '/' + f'{name}_out.txt'
        err_path_name = log_path + '/' + f'{name}_err.txt'
        out_log_file = open(out_path_name, 'a')
        err_log_file = open(err_path_name, 'a')
        subprocess.run(command.split(','), env=env,
                       stdout=out_log_file, stderr=err_log_file)
        out_log_file.close()
        err_log_file.close()

    def create_executor_task(self, command=None, env=None,
                             name=None, log_path=None):
        logger.info('create_executor_task---start\n\n')
        try:
            result = self.loop.run_in_executor(
                self.executor, self.sub_process_command, *(command, env, name,
                                                           log_path))
        except Exception as tmp:
            logger.info('create_executor_task_exception')
            logger.exception(tmp)
            result = None
        return result

    def parse_env(self, env_string=None):
        result = {}
        for i in env_string.split(','):
            k, v = i.split('=')
            result[k] = v
        return result

    def parse(self, line_data):
        """
                crontab           name job env total_times
        example='*/2,*,*,*,*,* ceshi python,--name=12 aa=123,bb=345 10'
        """
        try:
            cron, name, command, *env_total = line_data.split(' ')
            if len(env_total) == 2:
                env, total_times = env_total
                total_times = int(total_times)
            else:
                env = env_total[0]
                total_times = None
            job = self.parse_cron(cron=cron, name=name,
                                  total_times=total_times)
            if job is not None:
                env = self.parse_env(env_string=env)
                job.go(self.create_executor_task, command=command,
                       env=env, name=name, log_path=self.log_path)
            return job
        except Exception as tmp:
            logger.info('cron file format error')
            logger.exception(tmp)
            return None

    def parse_cron(self, cron=None, name=None, total_times=None):
        minute, hour, day, week, month, year = [
            i.strip() for i in cron.split(',')]
        year_every, year_at_time = self.parse_detail(year)
        month_every, month_at_time = self.parse_detail(month)
        week_every, week_at_time = self.parse_detail(week)
        day_every, day_at_time = self.parse_detail(day)
        hour_every, hour_at_time = self.parse_detail(hour)
        minute_every, minute_at_time = self.parse_detail(minute)

        tmp_job = CronJob(name=name, run_total=total_times)
        if (year_at_time and month_at_time and day_at_time and
                hour_at_time and minute_at_time):
            tmp_job = tmp_job.at(
                f"{year_at_time}-{month_at_time}-{day_at_time}\
                     {hour_at_time}:{minute_at_time}")
            return tmp_job

        if month != '*':
            if month_every is None:
                month_every = 1
            tmp_job = tmp_job.every(month_every)
            if day_at_time is not None:
                tmp_job = tmp_job.month_day(day_at_time)
            if hour_at_time is not None and minute is not None:
                tmp_job = tmp_job.at_time(f'{hour_at_time}:{minute_at_time}')
        elif week != '*':
            if week_every is None:
                month_every = 1
            if week_at_time is not None:
                tmp_job = tmp_job.week_day(week_at_time)
            if hour_at_time is not None and minute is not None:
                tmp_job = tmp_job.at_time(f'{hour_at_time}:{minute_at_time}')
        elif day != '*':
            if day_every is None:
                day_every = 1
            tmp_job = tmp_job.every(day_every).day
            if hour_at_time is not None and minute is not None:
                tmp_job = tmp_job.at_time(f'{hour_at_time}:{minute_at_time}')
        elif hour != '*':
            if hour_every is None:
                hour_every = 1
            tmp_job = tmp_job.every(hour_every).hour
            if minute is not None:
                tmp_job = tmp_job.at_time(f':{minute_at_time}')
        elif minute != '*':
            if minute_every is None:
                minute_every = 1
            tmp_job = tmp_job.every(minute_every).minute
        if tmp_job.unit:
            return tmp_job
        else:
            return None

    def parse_detail(self, data=None):
        data = data.split('/')
        every = None
        at_time = None
        if len(data) > 1:
            f_data, every = data
        else:
            at_time = data[0]
        if every is not None:
            if '*' not in every:
                every = int(every)
        if at_time is not None:
            if '*' not in at_time:
                at_time = int(at_time)
        return every, at_time

    def gen_job(self, data=None):
        pass

    async def run(self, schedule=None):
        try:
            jobs = await self.load()
            for job in jobs:
                if isinstance(job, CronJob):
                    self.add_job_schedule(job, schedule)
            print(schedule.jobs)
        except KeyboardInterrupt:
            logger.info('keyboard exit')
            self.executor.shutdown()

    @staticmethod
    def add_job_schedule(job, schedule):
        schedule.add_job(job)


class FileJobLoader(JobLoader):

    def __init__(self, file_path=None, **kwargs):
        super(FileJobLoader, self).__init__(**kwargs)
        self.file_path = file_path

    async def load(self):
        result = []
        if self.file_path:
            file = open(self.file_path, 'r')
            crons = [i.strip('\n').strip() for i in file.readlines()]
            for i in crons:
                tmp_cron = self.parse(i)
                if tmp_cron is not None:
                    result.append(tmp_cron)
        return result
