## aio.py

"""utilities for asynchronous applications"""

import asyncio as aio
from contextlib import contextmanager
from .naming import export, export_annotated
from typing import abstractmethod, Callable, Optional, Union
from typing_extensions import Annotated, Any, TypeAlias, ContextManager, Protocol


TimeoutArg: Annotated[TypeAlias, "Generalized timeout value"] = Union[int, float, bool]


class LockType(Protocol):
    """protocol class for type validation within lock applications"""

    # fmt: off
    @abstractmethod
    def acquire(
        blocking: Optional[bool] = True,
        timeout: Optional[TimeoutArg] = -1
    ) -> bool:
        '''abstract protocol method for lock.acquire()'''
        return NotImplemented
    # fmt: on

    @abstractmethod
    def release():
        """abstract protocol method for lock.release()"""
        return NotImplemented


@contextmanager
def lock_context(
    lock: LockType, blocking: Optional[bool] = True, timeout: Optional[TimeoutArg] = -1
):
    """Lock context implementation for call_sync

    ## Usage

    This context manager will try to acquire the provided `lock`.
    The `blocking` and `timeout` argument values will be provided
    in the call to `lock.acquire()`.

    Once the call to `lock.acquire()` has returned, then the return
    value from the `acquire()` call will be yielded from the context
    manager. This value will be denoted here as the `got` flag.

    On exit from the context manager, the `lock` will be released if
    the `got` flag represents a _truthy_ value.

    ## Implementation Notes

    - For applications where the `lock` would be acquired within a blocking
      call and without timeout, then it may be recommended to consider
      using the `lock` object directly as a context manager.
    """

    got = False
    try:
        got = lock.acquire(blocking=blocking, timeout=timeout)
        yield got
    finally:
        if got:
            lock.release()


@contextmanager
def identity_context(object: Optional[Any]):
    """identity context manager

    ## Usage

    This context manager will yield the provided `object`

    This implementation is provided for application as a _no-op_ context manager,
    for instance with `call_sync`
    """
    yield object


def call_sync(
    context: ContextManager, future: aio.Future, callback: Callable, *args, **kwargs
):
    """Call a synchronous function, recording the call completion state with a future

    If the provided `future` has not been cancelled, this function will call the
    `callback` with the provided `args` and `kwargs` within a context environment
    of the context manager provided as `context`.

    Whether through normal return or exception, completion  of the `callback` call
    will be recorded using the provided `future`.

    The `context` value should represent an instance of a context manager. This
    context manager should operate as to ensure that any resources required for
    the call will be held and/or available within the call.

    The `future` should be a newly initialized `asyncio.Future`, such that
    will be used exclusively for the duration of each single call. On
    successful completion of the callback, the future's `result()` value will
    be set to the value returned by the `callback`. On the event of an exception
    within the callback, the future's `exception()` value will be set to the
    received exception.

    If the future is cancelled before the callback can be called, then
    the callback will not be called and no further access will be
    performed on the `future`.

    ## Implementation Notes

    - For thread-safe applications, the provided context manager should
      operate as to ensure that all state fields of the provided `future`
      will be available exclusively within the context. This would include
      the `future.cancelled()`, `future.exception()`, and `future.result()`
      state fields. This may be approached, for instance, using an appropriate
     lock object as the `context` value.

    - For applications where a lock must be acquired within a definite
      timeout or without blocking, this function may be used together with
      a `lock_context` context manager.

    - For applications where the call to acquire a lock will block with an
      indefinite timeout, the lock object itself may generally serve as
      a context manager.

    - For applications where the state fields of the `future` may not be
      concurrently modified within any external thread -- generally, where the
     `future` may be accessed without any thread-safe blocks -- an `identity_context`
      may serve as a context manager implementation.

    **Example:** Using `call_sync` with an `asyncio` event loop

    ```python
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
    ```
    """
    ## Implementation notes:
    ##
    ## - When the lock context represents a lock that will be held for each test
    ##   or modification to the future's state fields and the future would not
    ##   produce a result without the lock_context held, then this function should
    ##   need to test the future.cancelled() state field exatctly once
    ##
    ## - As a known design limitation, this function does not accept a coroutine
    ##   or asynchronous function as the callback function. Coroutine state may
    ##   generally be managed in interacting directly with an the aio event loop.
    ##
    ## - This function does not in itself use an asynchronous call semantics. As
    ##   such, the function has not been defined as an asynchronous function.
    with context:
        if not future.cancelled():
            rslt = None
            try:
                rslt = callback(*args, **kwargs)
            except Exception as exc:
                future.set_exception(exc)
                return
            future.set_result(rslt)

# autopep8: off
# fmt: off
__all__ = []
export(__name__, LockType, lock_context, identity_context, call_sync)
export_annotated(__name__)
