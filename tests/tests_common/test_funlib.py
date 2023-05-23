## tests for pylaborate.common_staging.funlib

import pylaborate.common_staging.funlib as subject

from assertpy import assert_that
from pytest import mark
from random import randint
import sys
from types import ModuleType
from typing import Generator

## Notes
##
## pytest-dependency docs
##   https://pytest-dependency.readthedocs.io/en/stable/usage.html

##
## utility functions
##

def mock_module_name(sfxint = randint(0, id(__name__))) -> str:
    rndname = "mod_%x" % sfxint
    while rndname in sys.modules:
        rndname = "mod_%x" % id(rndname)
    return rndname

def mock_names_gen(count) -> Generator[str, None, None]:
    for n in range(0, count):
        yield mock_module_name(randint(0, id(n)))

def mock_names_list(count) -> list[str]:
    return [it for it in mock_names_gen(count)]


##
## tests
##

def test_get_module():
    ## test success
    builtins_module = sys.modules['builtins']

    assert_that(subject.get_module('builtins') is builtins_module)
    assert_that(subject.get_module(builtins_module) is builtins_module)

    ## test failure
    assert_that(subject.get_module).raises(subject.NameError).\
        when_called_with(mock_module_name())

@mark.dependency()
def test_export():
    mock_module = ModuleType(mock_module_name())
    mock_subnames = mock_names_list(4)
    cache = []
    subject.export(mock_module, cache, mock_subnames)
    assert_that(hasattr(mock_module, "__all__"))
    assert_that(set(mock_module.__all__)).is_equal_to(set(mock_subnames))

    subject.export(mock_module, cache, [mock_subnames])
    assert_that(set(mock_module.__all__)).is_equal_to(set(mock_subnames))

@mark.dependency(depends=['test_export'])
def test_module_all():
    ## setup for first test
    mock_mod = ModuleType(mock_module_name())
    mock_subnames = mock_names_list(4)
    cache = []
    subject.export(mock_mod, cache, mock_subnames)

    ## test primary functionality of module_all()

    ## - test when provided with a module object
    rslt_mod_all = subject.module_all(mock_mod)
    assert_that(set(rslt_mod_all)).is_equal_to(set(mock_subnames))

    ## - test when provided with a string module name
    rslt_named_all = subject.module_all(subject.__name__)
    assert_that(set(rslt_named_all)).is_equal_to(set(subject.__all__))

    ## test default handling when the module has no __all__ attr
    m_mock = ModuleType(mock_module_name())

    rslt_none = subject.module_all(m_mock)
    assert_that(rslt_none).is_equal_to(None)

    rslt_default = subject.module_all(m_mock, -1)
    assert_that(rslt_default).is_equal_to(-1)
