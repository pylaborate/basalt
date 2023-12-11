import asyncio as aio
from assertpy import assert_that
import os
from queue import Queue, Empty
import sys
from concurrent.futures import ThreadPoolExecutor
import traceback
from types import ModuleType
from typing import Any, Iterator, Optional, Mapping, Union

import pylaborate.common_staging.meta as subject


def each_class(
    context: Union[Mapping[str, Any], ModuleType, type] = sys.modules, cache: Optional[set] = None
) -> Iterator[type]:
    """Iterator for test_merge_mro_sys()"""
    if cache is None:
        cache = set()
    if id(context) not in cache:
        cache.add(id(context))
        if isinstance(context, type):
            yield context
            if hasattr(context, "__dict__"):
                yield from each_class(context.__dict__, cache)
        elif isinstance(context, ModuleType):
            if hasattr(context, "__dict__"):
                yield from each_class(context.__dict__, cache)
        elif isinstance(context, Mapping):
            for name in context:
                yield from each_class(context[name], cache)


def test_merge_mro_sys():
    """test `merge_mro()` onto a set of defined classes

    Ensure `merge_mro()` produces a value consistent
    onto the method resolution order for a set of
    defined classes.

    The set of input classes will be constructed by
    iterating across the set of modules accessible in
    `sys.modules` within the testing environment.
    """
    not_matching = Queue()
    failed = Queue()

    def test_module(name: str, not_matching: Queue, failed: Queue):
        for cls in tuple(each_class(sys.modules[name])):
            try:
                if tuple(subject.merge_mro((cls,))) != cls.__mro__:
                    not_matching.put(cls)
            except Exception as exc:
                failed.put((exc, cls,))

    test_loop = aio.get_event_loop_policy().new_event_loop()
    exc = ThreadPoolExecutor(24)

    async def run_test(nm_queue, failed_queue,
                       loop: aio.AbstractEventLoop,
                       executor: ThreadPoolExecutor):
        #
        # simple parallelization for test_module()
        #
        futures = (
            loop.run_in_executor(
                    executor, test_module, name, nm_queue, failed_queue
                ) for name in tuple(sys.modules.keys())
            )
        for rslt in await aio.gather(*futures, return_exceptions=True):
            if isinstance(rslt, Exception):
                traceback.print_exception(None, rslt, None, file=sys.stderr)

    test_loop.run_until_complete(run_test(not_matching, failed, test_loop, exc))

    failed_result = []
    while True:
        try:
            failed_result.append(failed.get(False))
        except Empty:
            break

    not_matching_result = []
    while True:
        try:
            not_matching_result.append(not_matching.get(False))
        except Empty:
            break

    assert_that(len(failed_result)).is_zero()
    assert_that(len(not_matching_result)).is_zero()


def test_merge_mro_new():
    class Cls_A:
        pass

    class Cls_A1(Cls_A):
        pass

    class Cls_A1_1(Cls_A1):
        pass

    class Cls_B(Cls_A1_1):
        pass

    class Cls_B_A1(Cls_B, Cls_A1):
        pass

    class Cls_C:
        pass

    running_pytest = "PYTEST_CURRENT_TEST" in os.environ

    input = [Cls_A, Cls_A1, Cls_A1_1, Cls_B, Cls_B_A1, Cls_C]
    orig = input.copy()
    input.reverse
    rslt = tuple(subject.merge_mro(input))
    for cls in orig:
        assert_that(cls in rslt).is_true()
        clsidx = rslt.index(cls)
        mros = cls.__mro__[1:]
        for mcls in mros:
            midx = rslt.index(mcls)
            assert_that(mcls in rslt).is_true()
            assert_that(midx).is_greater_than(clsidx)

    if not running_pytest:
        return rslt


if __name__ == "__main__":
    print("-- Testing merge_mro() onto sys.modules")
    test_merge_mro_sys()
    print("-- Testing merge_mro() for new class definitions")
    test_merge_mro_new()
