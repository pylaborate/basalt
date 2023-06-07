## tests for pylaborate.common_staging.naming

import pylaborate.common_staging.naming as subject

from assertpy import assert_that
from enum import Enum
from pytest import fixture, mark
from random import randint
import sys
from types import ModuleType
from typing import Generator, Sequence, Type

## Notes
##
## pytest-dependency docs
##   https://pytest-dependency.readthedocs.io/en/stable/usage.html

##
## utility functions
##


@fixture
def suffix_int() -> int:
    nmax = id(__name__)
    nmin = int(nmax / 2)
    return randint(nmin, nmax)


@fixture
def mock_module_name(suffix_int: int) -> str:
    rndname = "tmp_%x" % suffix_int
    while rndname in sys.modules:
        rndname = "tmp_%x" % id(rndname)
    return rndname


@fixture
def mock_module(mock_module_name: str) -> ModuleType:
    return ModuleType(mock_module_name)


def mock_names_gen(count: int) -> Generator[str, None, None]:
    for n in range(0, count):
        yield mock_module_name.__wrapped__(randint(0, id(n)))


@fixture
def n_names() -> int:
    return 4


@fixture
def mock_names(n_names: int) -> Sequence[str]:
    return tuple(mock_names_gen(n_names))


@fixture
def mock_class(mock_module_name) -> Type:
    return type(mock_module_name, (), dict())


##
## tests
##


@mark.dependency
def test_get_module(mock_module_name):
    ## test success
    builtins_module = sys.modules["builtins"]

    assert_that(subject.get_module("builtins") is builtins_module)
    assert_that(subject.get_module(builtins_module) is builtins_module)

    ## test failure
    assert_that(subject.get_module).raises(subject.NameError).when_called_with(
        mock_module_name
    )


@mark.dependency
def test_export_str_sequence(mock_module, mock_names):
    ## test export of a name sequence
    subject.export(mock_module, mock_names)
    assert_that("__all__").is_in(*dir(mock_module))
    assert_that(set(mock_module.__all__)).is_equal_to(set(mock_names))


def test_export_str_sequence_seq(mock_module, mock_names):
    ## test export of a nested name sequence
    subject.export(mock_module, [mock_names])
    assert_that("__all__").is_in(*dir(mock_module))
    assert_that(set(mock_module.__all__)).is_equal_to(set(mock_names))


def test_export_named(mock_module, mock_class):
    ## test export of a named object
    clsname = mock_class.__name__
    subject.export(mock_module, mock_class)
    assert_that("__all__").is_in(*dir(mock_module))
    assert_that(set(mock_module.__all__)).is_equal_to({clsname})


@mark.dependency(depends=["test_export_str_sequence"])
def test_export_str_tuple(mock_module, mock_names):
    ## test export of a named object within a module using a tuple __all__
    mock_module.__all__ = ()
    subject.export(mock_module, mock_names)
    assert_that("__all__").is_in(*dir(mock_module))
    assert_that(mock_module.__all__.__class__).is_in(tuple)
    assert_that(set(mock_module.__all__)).is_equal_to(set(mock_names))


@mark.dependency(depends=["test_export_str_sequence"])
def test_module_all(mock_module, mock_names):
    ## test primary functionality of module_all()

    ## - test default return when the module has no __all__ attr
    rslt_none = subject.module_all(mock_module)
    assert_that(rslt_none).is_equal_to(None)

    rslt_default = subject.module_all(mock_module, -1)
    assert_that(rslt_default).is_equal_to(-1)

    ## - test for a module object having an __all__ attr
    subject.export(mock_module, mock_names)
    rslt_mod_all = subject.module_all(mock_module)
    assert_that(set(rslt_mod_all)).is_equal_to(set(mock_names))

    ## - test when provided with a string module name
    rslt_named_all = subject.module_all(subject.__name__)
    assert_that(set(rslt_named_all)).is_equal_to(set(subject.__all__))


@mark.dependency(depends=["test_get_module"])
def test_bind_enum(mock_module):
    class MockConstA(Enum):
        MOCK_A = 0
        MOCK_B = "B"
        MOCK_C = "-B"

    subject.bind_enum(MockConstA, mock_module)
    mock_dir = dir(mock_module)
    members = MockConstA.__members__
    for member in members:
        assert_that(member).is_in(*mock_dir)
        assert_that(getattr(mock_module, member)).is_equal_to(members[member]._value_)


@mark.dependency(depends=["test_bind_enum"])
def test_export_enum(mock_module):
    class MockConstB(Enum):
        MOCK_C = -0.0
        MOCK_D = "D"
        MOCK_E = True

    subject.export_enum(MockConstB, mock_module)
    mock_dir = dir(mock_module)
    assert_that("__all__").is_in(*mock_dir)
    mock_all = mock_module.__all__
    assert_that(MockConstB.__name__).is_in(*mock_all)
    for member in MockConstB.__members__:
        assert_that(member).is_in(*mock_all)


@mark.dependency(depends=["test_get_module"])
def test_origin_name(mock_module):
    test_obj = mock_module_name
    obj_name = test_obj.__name__
    obj_expected_name = __name__ + "." + obj_name

    ## test for origin name of a defined object
    assert_that(subject.origin_name(test_obj)).is_equal_to(obj_expected_name)

    ## test for origin name of an aliased object
    sys.modules[mock_module.__name__] = mock_module
    setattr(mock_module, obj_name, test_obj)
    assert_that(subject.origin_name(getattr(mock_module, obj_name))).is_equal_to(
        obj_expected_name
    )

    ## test for origin name of an object defined in builtins
    assert_that(subject.origin_name(print)).is_equal_to("print")


@mark.dependency(depends=["test_get_module"])
def test_get_object():
    ## test for the relative name of an object in builtins
    assert_that(subject.get_object("print", "builtins")).is_in(print)
    ## test for the name of a module
    assert_that(subject.get_object(subject.__name__)).is_in(subject)
