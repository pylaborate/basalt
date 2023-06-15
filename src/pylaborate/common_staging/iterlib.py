## iterlib - pylaborate.common_staging
"""Iterator utilities"""

from .naming import export, export_annotated
from typing import Generator, Iterator, Mapping
from typing_extensions import TypeAlias, TypeVar


T = TypeVar("T")


Yields: TypeAlias = Generator[T, None, None]


class NoValue(ValueError):
    """ValueError indicating a value was expected,
    though no value was accessed"""

    pass


def first_gen(source: Iterator[T]) -> Yields[T]:
    """yields the first element of an iterator

    ## Exceptions

    - raises `NoValue` if the source yields no value
    """
    for elt in source:
        yield elt
        return
    raise NoValue("Source yielded no value", source)


def first(source: Iterator[T]) -> T:
    """returns the first element of an iterator"""
    for elt in first_gen(source):
        return elt


def last_gen(source: Iterator[T]) -> Yields[T]:
    """yields the last element from an iterator

    ## Exceptions

    - raises `NoValue` if the source yields no value
    """
    elt = None
    found = None
    for eltv in source:
        elt = eltv
        found = True
    if found is None:
        raise NoValue("Source yielded no value", source)
    else:
        yield elt


def last(source: Iterator[T]) -> T:
    """returns the last element from an iterator

    ## Exceptions

    - raises `NoValue` if the source yields no value
    """
    for elt in last_gen(source):
        return elt


def nth_gen(source: Iterator[T], n: int) -> Yields[T]:
    """yields the nth element from an iterator

    ## Exceptions

    - raises `NoValue` if `n` is greater than the number of
      elements yielded from the source, or if the source yields
      no value

    ## Known Limitations

    - Negative index values are not supported, at this time
    """
    counted = 0
    s = abs(int(n))
    if s != n:
        raise TypeError("Unsupported index value", n)
    for elt in source:
        if counted == s:
            yield elt
            return
        else:
            counted = counted + 1
    if counted is int(0):
        raise NoValue("Source yielded no value", source)
    else:
        # fmt: off
        raise NoValue("Count exceeded number of source elements",
                      n, counted, source)
        # fmt: on


def nth(source: Iterator[T], n: int) -> T:
    """returns the nth element from an iterator

    ## Exceptions

    - raises `NoValue` if the source yields no value

    ## Known Limitations

    - Negative index values are not supported, at this time
    """
    for elt in nth_gen(source, n):
        return elt


def merge_map(dest_mapping: Mapping, mapping: Mapping):
    """merge a source `mapping` into a `dest_mapping`

    ## Usage

    `dest_mapping`, `mapping`
    : a `Mapping` object. The `dest_mapping` must not be
      an immutable `Mapping`

    Returns the updated `dest_mapping`

    ## Overview

    `merge_map()` operates similar to `dict.update()`,
    though ensuring that any mapping values in the input
    `mapping` will be updated onto any corresponding map
    within the `dest_mapping`.

    In the case of a diferent type of value under a key
    existing in both mappings, similar to `dict.update()`
    the value from the input `mapping` will override.
    """
    for key, value in mapping.items():
        if isinstance(value, Mapping):
            if key in dest_mapping:
                dest = dest_mapping[key]
                if isinstance(dest, Mapping):
                    merge_map(dest_mapping[key], value)
                    continue
        dest_mapping[key] = value
    return dest_mapping


# autopep8: off
# fmt: off
__all__ = []
export(__name__, NoValue, first_gen, first, last_gen, last, nth_gen, nth, merge_map)

## export any TypeAlias values:
export_annotated(__name__)
