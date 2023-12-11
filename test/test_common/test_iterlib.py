## tests for pylaborate.common_staging.iterlib.util

from assertpy import assert_that
from pytest import fixture, mark

from typing import Mapping

import pylaborate.common_staging.iterlib as subject


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
def n_gen(n_range: range):
    return (n for n in n_range)


@fixture
def empty_range():
    return (n for n in range(0, 0))


##
## test generator return
##


@mark.dependency()
def test_first_gen(n_gen: subject.Yields[int], start):
    rslt = tuple(elt for elt in subject.first_gen(n_gen))
    assert_that(len(rslt)).is_equal_to(1)
    assert_that(rslt[0]).is_equal_to(start)


@mark.dependency()
def test_last_gen(n_gen, count):
    rslt = tuple(elt for elt in subject.last_gen(n_gen))
    assert_that(len(rslt)).is_equal_to(1)
    assert_that(rslt[0]).is_equal_to(count - 1)


@mark.dependency()
def test_nth_gen(n_gen, start, count):
    n = int(count / 2)
    rslt = tuple(elt for elt in subject.nth_gen(n, n_gen))
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
    rslt = subject.nth(n, n_range)
    assert_that(rslt).is_equal_to(n)


##
## test failure cases
##


@mark.dependency(depends=["test_first"])
def test_first_fail_no_value(empty_range):
    assert_that(subject.first).raises(RuntimeError).when_called_with(empty_range)


@mark.dependency(depends=["test_last"])
def test_last_fail_no_value(empty_range):
    assert_that(subject.last).raises(RuntimeError).when_called_with(empty_range)


@mark.dependency(depends=["test_nth"])
def test_nth_fail_no_value(empty_range):
    assert_that(subject.nth).raises(RuntimeError).when_called_with(1, empty_range)


@mark.dependency(depends=["test_nth"])
def test_nth_fail_exceeded(n_gen, count):
    assert_that(subject.nth).raises(RuntimeError).when_called_with(count, n_gen)

##
## other tests
##

def validate_map(rslt, input, dest):
    validated_keys = []
    assert_that(input).is_not_none()
    for key in input:
        assert_that(key in rslt).is_true()
        in_value = input[key]
        out_value = rslt[key]
        assert_that(out_value.__class__).is_equal_to(in_value.__class__)
        if isinstance(out_value, Mapping):
            dest_value = dest[key] if key in dest else None
            validate_map(out_value, dest_value, in_value)
        else:
            assert_that(out_value).is_equal_to(in_value)
        validated_keys.append(key)
    assert_that(dest).is_not_none()
    for key in set(dest.keys()).difference(set(validated_keys)):
        assert_that(key in rslt).is_true()
        dest_value = dest[key]
        out_value = rslt[key]
        assert_that(out_value.__class__).is_equal_to(dest_value.__class__)
        if isinstance(out_value, Mapping):
            validate_map(out_value, dest_value, None)
        else:
            assert_that(out_value).is_equal_to(dest_value)


def test_merge_map():
    m1 = dict(
        a = 1,
        b = dict(
            b1 = "b1",
            b2 = "b2"
        ),
        d = -1,
        e = dict(
            e1 = "e1"
        )
    )
    m2 = dict(
        b = dict(
            b1 = "b1_m2"
        ),
        c = 1,
        d = dict(
            d1 = "d1"
        )
    )
    rslt = subject.merge_map(m1, m2)
    validate_map(rslt, m1, m2)

