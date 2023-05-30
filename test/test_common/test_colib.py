from assertpy import assert_that
from pytest import fixture
from random import randint
from typing import List

import pylaborate.common_staging.colib as subject


def identity(obj):
    return obj


def list_gen(count: int, nduplicate: int) -> List[int]:
    assert count > nduplicate * 2, "count must be greater than nduplicate * 2"

    ## generate a list of random integers of length `count` and range [0..count]
    ## such that the list will include `nduplicate` number of non-unique elements
    ##
    ## known limitations:
    ## - This approach for collection of randomzed values and randomized placement of
    ##   duplicate values is limited. It may often result in a sequential placement of
    ##   low-index duplicate values - an effect that may be obscured after randomized
    ##   placement of high-index values. It was considered to be of appropriate quality
    ##   for localized usage in a test fixture.

    dups = [-5] * nduplicate
    end = count - 1
    dupend = int(count / 2)
    dup_n = randint(0, dupend)
    dupcount = nduplicate - 1
    while dupcount >= 0:
        while dup_n in dups:
            dup_n = randint(0, dupend)
        dups[dupcount] = dup_n
        dupcount = dupcount - 1

    rslt = []
    rnd = randint(0, end)
    idx = end
    chkidx = 0
    dupcount = nduplicate - 1
    thunk = True
    while idx >= 0:
        while thunk or (rnd in rslt):
            rnd = randint(0, end)
            thunk = False
        thunk = True
        rslt.append(rnd)
        if chkidx in dups:
            idx = idx - 1
            ridx = randint(0, len(rslt))
            rslt.insert(ridx, rnd)
        chkidx = chkidx + 1
        idx = idx - 1
    return rslt


@fixture
def count():
    return 24


@fixture
def nduplicate():
    return 8


@fixture
def dups_list(count, nduplicate):
    return list_gen(count, nduplicate)


def test_uniq(dups_list: List[int]):
    data_copy = dups_list.copy()
    data_tuple = tuple(data_copy)
    ## utilizing some properties of the set constructor here
    data_set = set(data_tuple)

    ## uniq() will modify the dups_list in-place
    subject.uniq(dups_list, hash_call=identity)

    result_tuple = tuple(dups_list)
    result_set = set(dups_list)

    assert_that(result_tuple).is_not_equal_to(data_tuple)
    assert_that(len(result_tuple)).is_equal_to(len(result_set))
    assert_that(result_set).is_equal_to(data_set)


def test_uniq_forward(dups_list: List[int]):
    data_copy = dups_list.copy()
    data_tuple = tuple(data_copy)
    ## utilizing some properties of the set constructor here
    data_set = set(data_tuple)

    ## uniq() will modify the dups_list in-place
    subject.uniq(dups_list, hash_call=identity, reverse=False)

    result_tuple = tuple(dups_list)
    result_set = set(dups_list)

    assert_that(result_tuple).is_not_equal_to(data_tuple)
    assert_that(len(result_tuple)).is_equal_to(len(result_set))
    assert_that(result_set).is_equal_to(data_set)


def test_uniq_gen(dups_list):
    data_copy = dups_list.copy()
    data_tuple = tuple(data_copy)
    data_set = set(data_tuple)

    result_gen = subject.uniq_gen(data_tuple, hash_call=identity)

    result_tuple = tuple(result_gen)
    result_set = set(result_tuple)

    assert_that(result_tuple).is_not_equal_to(data_tuple)
    assert_that(len(result_tuple)).is_equal_to(len(result_set))
    assert_that(result_set).is_equal_to(data_set)
