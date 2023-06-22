from contextlib import asynccontextmanager
from asyncio import Lock, Event

class RWLock(object):
    """ RWLock class; this is meant to allow an object to be read from by
        multiple threads, but only written to by a single thread at a time. See:
        https://en.wikipedia.org/wiki/Readers%E2%80%93writer_lock

        Usage:

            from rwlock import RWLock

            my_obj_rwlock = RWLock()

            # When reading from my_obj:
            with my_obj_rwlock.r_locked():
                do_read_only_things_with(my_obj)

            # When writing to my_obj:
            with my_obj_rwlock.w_locked():
                mutate(my_obj)
    """

    def __init__(self):

        self.w_lock = Lock()
        self._lock = Lock()
        self.num_r = 0

        self.w_released = Event()
        self.w_released.set()

    # ___________________________________________________________________
    # Reading methods.

    async def r_acquire(self):
        await self.w_released.wait()

        async with self._lock:
            self.num_r += 1
            if self.num_r == 1:
                await self.w_lock.acquire()

    def r_release(self):
        assert self.num_r > 0
        #async with self._lock:
        self.num_r -= 1
        if self.num_r == 0:
            self.w_lock.release()

    @asynccontextmanager
    async def r_locked(self):
        """ This method is designed to be used via the `with` statement. """
        try:
            await self.r_acquire()
            yield
        finally:
            self.r_release()

    # ___________________________________________________________________
    # Writing methods.

    async def w_acquire(self):
        await self.w_released.wait()
        self.w_released.clear()

        await self.w_lock.acquire()

    def w_release(self):
        self.w_lock.release()
        self.w_released.set()

    @asynccontextmanager
    async def w_locked(self):
        """ This method is designed to be used via the `with` statement. """
        try:
            await self.w_acquire()
            yield
        finally:
            self.w_release()