## tests for pylaborate.common_staging.iterlib.util

from assertpy import assert_that
from pytest import fixture, mark

import pylaborate.common_staging.iterlib.util as subject


@fixture
def start():
    return 0


@fixture
def count():
    return 1024


@fixture
def n_range(start, count):
    return range(start, start + count)


@fixture
def empty_range():
    return range(0, 0)


##
## test generator return
##


@mark.dependency()
def test_first_gen(n_range, start):
    rslt = tuple(elt for elt in subject.first_gen(n_range))
    assert_that(len(rslt)).is_equal_to(1)
    assert_that(rslt[0]).is_equal_to(start)


@mark.dependency()
def test_last_gen(n_range, count):
    rslt = tuple(elt for elt in subject.last_gen(n_range))
    assert_that(len(rslt)).is_equal_to(1)
    assert_that(rslt[0]).is_equal_to(count - 1)


@mark.dependency()
def test_nth_gen(n_range, start, count):
    n = int(count / 2)
    rslt = tuple(elt for elt in subject.nth_gen(n_range, n))
    assert_that(len(rslt)).is_equal_to(1)
    assert_that(rslt[0]).is_equal_to(n)


##
## test non-iterator return
##


@mark.dependency(depends=["test_first_gen"])
def test_first(n_range, start):
    rslt = subject.first(n_range)
    assert_that(rslt).is_equal_to(start)


@mark.dependency(depends=["test_last_gen"])
def test_last(n_range, count):
    rslt = subject.last(n_range)
    assert_that(rslt).is_equal_to(count - 1)


@mark.dependency(depends=["test_nth_gen"])
def test_nth(n_range, start, count):
    n = int(count / 2)
    rslt = subject.nth(n_range, n)
    assert_that(rslt).is_equal_to(n)


##
## test failure cases
##


@mark.dependency(depends=["test_first"])
def test_first_fail_no_value(empty_range):
    assert_that(subject.first).raises(subject.NoValue).when_called_with(empty_range)


@mark.dependency(depends=["test_last"])
def test_last_fail_no_value(empty_range):
    assert_that(subject.last).raises(subject.NoValue).when_called_with(empty_range)


@mark.dependency(depends=["test_nth"])
def test_nth_fail_no_value(empty_range):
    assert_that(subject.nth).raises(subject.NoValue).when_called_with(empty_range, 1)


@mark.dependency(depends=["test_nth"])
def test_nth_fail_exceeded(n_range, count):
    assert_that(subject.nth).raises(subject.NoValue).when_called_with(n_range, count)
