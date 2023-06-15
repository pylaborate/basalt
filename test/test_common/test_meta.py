
from assertpy import assert_that
import os
import sys
from types import ModuleType

import pylaborate.common_staging.meta as subject


def each_class(context=sys.modules, cache=[]):
    if id(context) not in cache:
        cache.append(id(context))
        match context:
            case type():
                yield context
                yield from each_class(context.__dict__, cache)
            case ModuleType():
                yield from each_class(context.__dict__, cache)
            case dict():
                for name in context:
                    yield from each_class(context[name], cache)

def test_merge_mro_sys():
    ## an exhaustive test for merge_mro()
    ##
    ## this unit test is implemented as to ensure that merge_mro( ) will
    ## produce a value consistent onto the actual method resolution order,
    ## for all publicly accessible classes within the testing environment.
    not_matching = []
    failed = []
    for name in sys.modules:
        for cls in each_class(sys.modules[name]):
            try:
                if tuple(subject.merge_mro((cls,))) != cls.__mro__:
                    not_matching.append(cls)
            except Exception:
                failed.append(cls)
    assert_that(len(failed)).is_zero()
    assert_that(len(not_matching)).is_zero()


def test_merge_mro_custom():

    class cls_a:
        ## one of the two most generic classes, in this example
        pass

    class cls_a1(cls_a):
        pass

    class cls_a1_1(cls_a1):
        pass

    class cls_b(cls_a1_1):
        pass

    class cls_ba1(cls_b, cls_a1):
        pass

    class cls_c():
        ## second of the two most generic classes
        pass

    running_pytest = "PYTEST_CURRENT_TEST" in os.environ

    ## Implementation note: Given a set of classes of arbitrary
    ## "generic-ness", the subset of the "most generic" classes
    ## will be yielded from merge_mro() effectively in the order in
    ## which those "most generic" classes were present in the provided
    ## base class sequence.
    ##
    ## e.g if cls_c was listed before cls_a below, it would also be
    ## present before cls_a, in the result from merge_mro()

    input = [cls_a, cls_a1, cls_a1_1, cls_b, cls_ba1, cls_c]
    orig = input.copy()
    input.reverse
    rslt = tuple(subject.merge_mro(input))
    for cls in orig:
        assert_that(cls).is_in(*rslt)
        clsidx = rslt.index(cls)
        bases = cls.__mro__[1:]
        for basec in bases:
            if not running_pytest:
                ## verbose output for direct tests
                ## e.g in an ipython environment
                print(f"test base @ {basec} onto {cls}")
            baseidx = rslt.index(basec)
            assert_that(baseidx).is_greater_than(clsidx)

    if not running_pytest:
        return rslt
