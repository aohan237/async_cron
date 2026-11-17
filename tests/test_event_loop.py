import asyncio
from concurrent.futures import ProcessPoolExecutor
import contextlib
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

from async_cron.job import CronJob
from async_cron.job_loader import FileJobLoader, JobLoader
from async_cron.schedule import Scheduler


class TestEventLoopHandling(unittest.TestCase):
    """All scheduler objects must support construction without a current loop."""

    constructors = (CronJob, Scheduler, JobLoader, FileJobLoader)

    def setUp(self):
        asyncio.set_event_loop(None)
        self.loops = []
        self.loaders = []
        self.original_new_event_loop = asyncio.new_event_loop
        self.loop_patch = mock.patch('asyncio.new_event_loop',
                                     side_effect=self.new_loop)
        self.loop_patch.start()

    def tearDown(self):
        try:
            for loader in self.loaders:
                loader.executor.shutdown(wait=True)
            for loop in self.loops:
                if not loop.is_closed():
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    if pending:
                        loop.run_until_complete(asyncio.gather(
                            *pending, return_exceptions=True))
                    loop.close()
        finally:
            self.loop_patch.stop()
            asyncio.set_event_loop(None)

    def new_loop(self):
        loop = self.original_new_event_loop()
        self.loops.append(loop)
        return loop

    def construct(self, constructor, **kwargs):
        if issubclass(constructor, JobLoader):
            kwargs.setdefault('log_path', '.')
        obj = constructor(**kwargs)
        if isinstance(obj, JobLoader):
            self.loaders.append(obj)
        return obj

    def assert_creates_loop(self, constructor):
        obj = self.construct(constructor)
        self.assertIsInstance(obj.loop, asyncio.AbstractEventLoop)
        self.assertFalse(obj.loop.is_closed())
        self.assertIs(asyncio.get_event_loop(), obj.loop)

    def test_cronjob_creates_event_loop_outside_running_loop(self):
        self.assert_creates_loop(CronJob)

    def test_scheduler_creates_event_loop_outside_running_loop(self):
        self.assert_creates_loop(Scheduler)

    def test_jobloader_creates_event_loop_outside_running_loop(self):
        self.assert_creates_loop(JobLoader)

    def test_filejobloader_creates_event_loop_outside_running_loop(self):
        self.assert_creates_loop(FileJobLoader)

    def test_explicit_loop_is_used_without_changing_current_loop(self):
        current = self.new_loop()
        explicit = self.new_loop()
        asyncio.set_event_loop(current)
        with mock.patch('asyncio.get_event_loop',
                        side_effect=AssertionError('explicit loop ignored')):
            for constructor in self.constructors:
                with self.subTest(constructor=constructor.__name__):
                    self.assertIs(self.construct(constructor, loop=explicit).loop,
                                  explicit)
        self.assertIs(asyncio.get_event_loop(), current)

    def test_existing_loop_is_reused(self):
        current = self.new_loop()
        asyncio.set_event_loop(current)
        for constructor in self.constructors:
            with self.subTest(constructor=constructor.__name__):
                self.assertIs(self.construct(constructor).loop, current)
        self.assertEqual(len(self.loops), 1)

    def test_running_loop_is_used_inside_coroutine(self):
        async def check():
            for constructor in self.constructors:
                with self.subTest(constructor=constructor.__name__):
                    obj = self.construct(constructor)
                    self.assertIs(obj.loop, asyncio.get_running_loop())

        asyncio.run(check())

    def test_objects_share_one_implicitly_created_loop(self):
        objects = [self.construct(constructor)
                   for constructor in self.constructors]
        self.assertTrue(all(obj.loop is objects[0].loop for obj in objects))
        self.assertEqual(len(self.loops), 1)

    def test_construction_after_asyncio_run(self):
        for constructor in self.constructors:
            with self.subTest(constructor=constructor.__name__):
                asyncio.run(asyncio.sleep(0))
                self.assert_creates_loop(constructor)

    def test_worker_thread_installs_its_own_loop(self):
        for constructor in self.constructors:
            with self.subTest(constructor=constructor.__name__):
                results = []
                errors = []

                def check():
                    try:
                        obj = self.construct(constructor)
                        results.append(obj.loop is asyncio.get_event_loop())
                    except Exception as error:
                        errors.append(error)

                worker = threading.Thread(target=check)
                worker.start()
                worker.join(timeout=5)
                self.assertFalse(worker.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(results, [True])
        with self.assertRaises(RuntimeError):
            asyncio.get_event_loop()

    def test_implicit_loop_executes_sync_and_async_jobs(self):
        scheduler = self.construct(Scheduler)
        seen = []

        async def callback():
            await asyncio.sleep(0)
            seen.append('async')

        for name, function in [('sync', lambda: seen.append('sync')),
                               ('async', callback)]:
            job = self.construct(CronJob, name=name, run_total=1)
            scheduler.add_job(job.second.go(function))

        async def check():
            await scheduler.check_jobs()
            tasks = asyncio.all_tasks() - {asyncio.current_task()}
            await asyncio.gather(*tasks)
            await scheduler.check_jobs()

        scheduler.loop.run_until_complete(check())
        self.assertEqual(seen, ['sync', 'async'])
        self.assertEqual(scheduler.jobs, {})

    def test_scheduler_repeats_and_removes_jobs(self):
        scheduler = self.construct(Scheduler, check_interval=0.005)
        seen = []
        job = self.construct(CronJob, run_total=3)
        scheduler.add_job(job.every(0.02).second.go(seen.append, 'ran'))

        async def check():
            runner = asyncio.create_task(scheduler.start())
            try:
                async def wait_for_runs():
                    while len(seen) < 3:
                        await asyncio.sleep(0.005)

                await asyncio.wait_for(wait_for_runs(), timeout=2)
            finally:
                runner.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await runner

        scheduler.loop.run_until_complete(check())
        self.assertEqual(seen, ['ran'] * 3)
        self.assertEqual(scheduler.jobs, {})

    def test_standalone_loaders_execute_subprocess(self):
        for constructor in (JobLoader, FileJobLoader):
            for thread in (True, False):
                with self.subTest(constructor=constructor.__name__, thread=thread):
                    asyncio.set_event_loop(None)
                    with mock.patch('async_cron.job_loader.ProcessPoolExecutor',
                                    side_effect=lambda: ProcessPoolExecutor(
                                        max_workers=1)):
                        loader = self.construct(constructor, thread=thread)
                    with tempfile.TemporaryDirectory() as directory:
                        future = loader.create_executor_task(
                            command=sys.executable + ',-c,print("loader-ok")',
                            env=os.environ.copy(), name='probe',
                            log_path=directory)
                        self.assertIsNotNone(future)
                        loader.loop.run_until_complete(
                            asyncio.wait_for(future, timeout=10))
                        self.assertEqual(
                            (Path(directory) / 'probe_out.txt').read_text(),
                            'loader-ok\n')
                        self.assertEqual(
                            (Path(directory) / 'probe_err.txt').read_text(), '')
                    loader.executor.shutdown(wait=True)

    def test_standalone_filejobloader_loads_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'crontab'
            path.write_text('')
            loader = self.construct(FileJobLoader, file_path=str(path))
            self.assertEqual(loader.loop.run_until_complete(loader.load()), [])


if __name__ == '__main__':
    unittest.main()
