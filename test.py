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
job2 = CronJob(name='exact', tolerance=100).at(
    "2019-01-15 16:12").go(tt, (5), age=99)
job3 = CronJob(name='very_hour').every().hour.at(
    ":44").go(tt, (5), age=99)

job3 = CronJob(name='hour').every().hour.at(
    ":00").go(tt, (5), age=99)
job4 = CronJob(name='minute').every(1).minute.go(tt, (5), age=99)
job4 = CronJob(name='weekday').weekday(2).at("11:18").go(tt, (5), age=99)
job4 = CronJob(name='monthday').monthday(16).at("11:22").go(tt, (5), age=99)
job4 = CronJob(name='monthday').every(5).monthday(
    16).at("11:22").go(tt, (5), age=99)


msh.add_job(myjob)
msh.add_job(job2)
msh.add_job(job3)
msh.add_job(job4)


loop = asyncio.get_event_loop()

try:
    loop.run_until_complete(msh.start())
except KeyboardInterrupt:
    print('exit')
