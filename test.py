import asyncio

from async_cron.job import CronJob
from async_cron.schedule import Scheduler


async def test(*args, **kwargs):
    print(args, kwargs)


def tt(*args, **kwargs):
    print(args, kwargs)


msh = Scheduler()
myjob = CronJob(name='test', run_total=3).every(
    5).second.go(test, (1, 2, 3), name=123)
job2 = CronJob(name='tt', tolerance=100).every().at(
    "2019-01-15 16:12").go(tt, (5), age=99)

msh.add_job(myjob)
msh.add_job(job2)


loop = asyncio.get_event_loop()

loop.run_until_complete(msh.start())
