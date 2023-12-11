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
    """Lock context implementation for call_sync"""

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
    """Call a synchronous function within a context manager, recording the call
    completion state with an asyncio Future
    """
    with context:
        if not future.done():
            try:
                future.set_result(callback(*args, **kwargs))
            except (aio.CancelledError, aio.InvalidStateError):
                pass
            except (Exception, BaseException) as exc:
                future.set_exception(exc)

# autopep8: off
# fmt: off
__all__ = []
export(__name__, LockType, lock_context, identity_context, call_sync)
export_annotated(__name__)
