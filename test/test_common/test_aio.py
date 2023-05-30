import asyncio as aio
from assertpy import assert_that
from concurrent.futures import ThreadPoolExecutor
from pytest import mark
import selectors
import sys
import threading
import time

import pylaborate.common_staging.aio as subject

@mark.dependency()
def test_lock_context():
    ## trivial test for lock_context application
    lock = threading.Lock()
    with subject.lock_context(lock) as got:
        assert_that(got).is_true()
        assert_that(lock.locked()).is_true()


@mark.dependency(depends=['test_lock_context'])
def test_call_sync():
    ## This function performs a small number of independent tests,
    ## using a few common local variarbles and functions

    lock = threading.Lock()
    context = subject.lock_context(lock)
    future = aio.Future()
    cb_called = False

    def generic_callback():
        ## a synchronous call for tests,
        ## returning a known value
        ## after setting cb_called
        nonlocal cb_called
        cb_called = True
        return 12321

    class LocalException(Exception):
        pass

    def throwing_callback():
        ## a synchronous call for tests,
        ## throwing a known exception
        ## after setting cb_called
        nonlocal cb_called
        cb_called = True
        raise LocalException("Exception Thrown")

    ##
    ## test for a direct callback => future process under call_sync
    ##

    subject.call_sync(context, future, generic_callback)
    assert_that(cb_called).is_true()
    assert_that(future.result()).is_equal_to(12321)

    ##
    ## test for context application under a concurrent.futures
    ## executor in aio, dispatching to an aio loop
    ##

    executor = ThreadPoolExecutor(2)

    loop = aio.get_event_loop()
    future = aio.Future()
    cb_called = False

    def aio_runner(loop, lock, future, the_cb):
        ## a common dispatch function for the following tests
        context = subject.lock_context(lock)
        loop.run_until_complete(subject.call_sync(context, future, the_cb))

    with subject.lock_context(lock):
        ## in effect, this should ensure that the loop is in fact running
        loop.run_in_executor(executor, aio_runner, loop, lock, future, generic_callback)

    loop.run_until_complete(future)
    assert_that(future.cancelled()).is_false()
    assert_that(future.exception()).is_none()
    assert_that(future.done()).is_true()
    assert_that(cb_called).is_true()
    assert_that(future.result()).is_equal_to(12321)

    ##
    ## test for exception capture under call_sync()
    ## using a concurrent.futures executor in aio,
    ## by dispatching to an aio loop
    ##

    future = aio.Future()
    cb_called = False

    with subject.lock_context(lock):
        loop.run_in_executor(
            executor, aio_runner, loop, lock, future, throwing_callback
        )

    exc_propogated = False
    try:
        loop.run_until_complete(future)
    except LocalException:
        exc_propogated = True
    assert_that(exc_propogated).is_true()
    assert_that(future.cancel()).is_false()
    assert_that(future.done()).is_true()
    assert_that(future.exception()).is_instance_of(LocalException)
    assert_that(cb_called).is_true()

    ##
    ## test for call_sync under a concurrent.futures executor in aio,
    ## with future cancellation before dispatch to the aio loop
    ##

    interval = sys.getswitchinterval()

    def block_on(fut):
        nonlocal interval
        while not fut.done():
            time.sleep(interval)

    future = aio.Future()
    cb_called = False

    with subject.lock_context(lock):
        ## cancelling the future here, to minimize complexity
        ## in the test infrastructure
        future.cancel()

    loop.run_in_executor(executor, aio_runner, loop, lock, future, generic_callback)

    block_on(future)

    assert_that(future.cancelled()).is_true()
    exception = False
    try:
        exception = future.exception()
    except aio.CancelledError:
        pass
    finally:
        assert_that(exception).is_false()
    assert_that(cb_called).is_false()

    ##
    ## test for call_sync under a trivial threading application
    ##

    future = aio.Future()
    cb_called = False

    def thr_run(lock, future, top_cb):
        def sub_call_threaded(sub_lock, sub_future, sub_cb):
            context = subject.lock_context(sub_lock)
            loop = aio.SelectorEventLoop(selectors.SelectSelector())

            ## TBD define one  @asynccontextmanager 'coro' 
            ##  in lieu of defining one or more coro_shim
            async def coro_shim():
                nonlocal context, sub_future, sub_cb
                return subject.call_sync(context, sub_future, sub_cb)

            if loop.is_running():
                loop.call_soon(coro_shim())
            else:
                loop.run_until_complete(coro_shim())

        sub_thr = threading.Thread(
            target=sub_call_threaded, args=(lock, future, top_cb)
        )
        sub_thr.start()
        sub_thr.join()

    ## ensuring some degree of separation between the active thread
    ## and the thread where the context manager will be applied, under
    ## each respective aio loop
    runner_thr = threading.Thread(
        target=loop.run_in_executor,
        args=(executor, thr_run, lock, future, generic_callback),
    )
    runner_thr.start()
    runner_thr.join()

    block_on(future)

    assert_that(future.cancelled()).is_false()
    assert_that(future.exception()).is_none()
    assert_that(future.result()).is_equal_to(12321)
    assert_that(cb_called).is_true()


@mark.dependency(depends=['test_call_sync'])
def test_call_sync_example():
    ## test for the example code provided in the call_sync docstring
    import asyncio as aio
    from pylaborate.common_staging import call_sync, lock_context
    import random
    import sys
    import threading

    def hpyth(a, b):
        ## function to call under an event loop
        return (a**2 + b**2)

    def dispatch_call(a, b, future, loop, lock, timeout):
        context = lock_context(lock, timeout = timeout)
        loop.run_until_complete(call_sync(context, future, hpyth, a, b))

    loop = aio.get_event_loop()
    fut_lock = threading.Lock()
    future = aio.Future()
    a = random.randint(0, 1023)
    b = random.randint(0, 1023)
    timeout = sys.getswitchinterval()

    with lock_context(fut_lock):
        loop.run_in_executor(None, dispatch_call, a, b, future, loop, fut_lock, timeout)

    ## ensure the callback has completed, before accessing the result
    loop.run_until_complete(future)

    assert future.result() == hpyth(a, b)

