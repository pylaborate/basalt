# tests for pylaborate.common_staging.demap

from assertpy import assert_that
from datetime import datetime
import os
from pytest import fixture, mark

import pylaborate.common_staging.demap as subject

##
## Utility Functions
##


def popd(dct, key):
    val = dct[key]
    del dct[key]
    return val


def ensure_mapping_len(mapping, nr):
    assert_that(len(mapping)).is_equal_to(nr)
    assert_that(len(mapping.keys())).is_equal_to(nr)
    assert_that(len(mapping.values())).is_equal_to(nr)
    assert_that(len(mapping.items())).is_equal_to(nr)

def ensure_mapping_nonmembership(mapping, key):
    assert_that(key in mapping).is_false()
    assert_that(mapping.get(key)).is_none()
    assert_that(lambda key: mapping[key]).raises(KeyError).when_called_with(key)

def ensure_mapping_membership(mapping, key, value):
    assert_that(key in mapping).is_true()
    assert_that(key in mapping.keys()).is_true()
    assert_that(value in mapping.values()).is_true()
    assert_that(mapping[key]).is_equal_to(value)

def ensure_new_mapping_member(mapping, key, value):
    ensure_mapping_nonmembership(mapping, key)
    initial = len(mapping)
    mapping[key] = value
    ensure_mapping_len(mapping, initial+1)
    ensure_mapping_membership(mapping, key, value)

def ensure_mapping_value_update(mapping, key, value):
    initial = mapping[key]
    mapping[key] = value
    assert_that(mapping[key]).is_not_equal_to(initial)
    assert_that(mapping[key]).is_equal_to(value)

def ensure_demap_value_remove(demap, key):
    value = demap[key]
    initlen = len(demap)
    assert_that(popd(demap, key)).is_equal_to(value)
    assert_that(key in demap).is_false()
    assert_that(key in demap.keys()).is_false()
    assert_that(value in demap.values()).is_false()
    assert_that(demap.get(key)).is_none()
    assert_that(lambda key: demap[key]).raises(KeyError).when_called_with(key)
    ensure_mapping_len(demap, initlen - 1)
    ensure_mapping_nonmembership(demap, key)
    return value

##
## Test Fixtures
##

@fixture
def count():
    if "TEST_BENCHMARK_COUNT" in os.environ:
        return int(os.environ["TEST_BENCHMARK_COUNT"])
    else:
        ## FIXME benchmarking these exhaustive tests vis a vis dict() mappings
        ## - less optimal by an order of magnitude, here
        return 127

@fixture
def demap():
    if "TEST_BENCHMARK_DICT" in os.environ:
        return dict()
    else:
        # return subject.Demap(bounded = count.__pytest_wrapped__.obj())
        return subject.Demap()



##
## Tests
##

def test_demap(count, demap):
    if isinstance(demap, subject.Demap):
        ## conditional dispatch for benchmarking vs dict()
        assert_that(demap.__missing__).raises(KeyError).when_called_with("anykey")

    ensure_mapping_len(demap, 0)
    ## FIXME, this is evaluating as None, not False:
    ##   "nonexistent" in demap
    ensure_mapping_nonmembership(demap, "nonexistent")

    ensure_new_mapping_member(demap, "firstkey", 5)
    ensure_mapping_value_update(demap, "firstkey", None)
    ensure_mapping_value_update(demap, "firstkey", 15)
    ensure_mapping_len(demap, 1)

    ensure_demap_value_remove(demap, "firstkey")
    ensure_mapping_len(demap, 0)

    keytab = dict()
    ## cache values for iteration testing
    keyseq = [False] * count
    valseq = [False] * count
    for n in range(0, count):
        key = "key_%x" % n
        keyseq[n] = key
        val = "value %d @ %s" % (n, datetime.utcnow().strftime("%X.%f"),)
        valseq[n] = val
        keytab[key] = val
        ## testing demap
        ensure_new_mapping_member(demap, key, val)

    ensure_mapping_len(demap, count)


    ## testing membership, after adding n items
    for key, value in keytab.items():
        ensure_mapping_membership(demap, key, value)

    ## testing forward and reverse iteration
    for key in demap:
        assert_that(key in keyseq).is_true()
        assert_that(demap[key] in valseq).is_true()
        assert_that(demap[key]).is_equal_to(keytab[key])
    for rkey in reversed(demap):
        assert_that(rkey in keyseq).is_true()
        assert_that(demap[rkey] in valseq).is_true()
        assert_that(demap[rkey]).is_equal_to(keytab[rkey])
    for key in demap.values():
        assert_that(value in valseq).is_true()
    for key, value in demap.items():
        assert_that(key in keyseq).is_true()
        assert_that(demap[key]).is_equal_to(keytab[key])
        assert_that(value in valseq).is_true()


    ## testing removal, after nth membership test
    for key in keytab:
        ensure_demap_value_remove(demap, key)

    ## nth testing for nonmembership
    for key in keytab:
        ensure_mapping_nonmembership(demap, key)

    ensure_mapping_len(demap, 0)

    ## cleanup
    # for key in keyseq:
    #     del keytab[key]

    ## FIXME
    ## - test [early] Demap.each_queued()
    ##
    ## - test initialization with initial dict
    ## - test initialization with list[list[a,b,]]
    ## - test Demap.update()
    ## - test Demap.copy()
    ## - test forward iteration
    ## - test reverse iteration


