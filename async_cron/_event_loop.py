import asyncio


def get_event_loop(loop=None):
    """Reuse the supplied/current loop, or install a new thread-local loop."""
    if loop is not None:
        return loop
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        # Python 3.14 no longer creates a loop implicitly. This also handles
        # worker threads and construction after asyncio.run() clears the loop.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop
