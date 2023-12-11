"""Iterator utilities"""

import inspect
from itertools import chain

from .naming import export

from typing import (
    AsyncGenerator, Callable, Generator, Iterator,
    Optional, Iterable, Mapping, Union
)
from typing_extensions import TypeAlias, TypeVar


T = TypeVar("T")


Yields: TypeAlias = Generator[T, None, None]
AsyncYields: TypeAlias = AsyncGenerator[T, None]


def ensure_gen(iter: Iterable[T]) -> Yields[T]:
    """Return a generator for an iterable object

    If `iter` is a generator, returns `iter`

    If `iter` is an Iterator, returns a generator onto `iter`

    Lastly, returns a generator onto a chained iterator for `iter`

    In the second and third cases, the generator will yield
    each successive element of `iter`
    """
    if inspect.isgenerator(iter):
        return iter
    elif isinstance(iter, Iterator):
        return (elt for elt in iter)
    else:
        return (elt for elt in chain(iter))


def first_gen(source: Yields[T]) -> Yields[T]:
    """yield the first value from a generator

    ### Exceptions

    raises StopIteration if the source yields no value
    """
    yield next(source)


def first(source: Iterable[T]) -> T:
    """return the first value from an iterable object

    ### Exceptions

    raises RuntimeError if the source yields no value"""
    return next(first_gen(ensure_gen(source)))


def last_gen(source: Iterable[T]) -> Yields[T]:
    """yield the last value from a generator

    ### Exceptions

    raises StopIteration if the source yields no value
    """
    elt = None
    found = None
    while True:
        try:
            elt = next(source)
            found = True
        except StopIteration:
            if found is None:
                raise
            else:
                yield elt
                return


def last(source: Iterable[T]) -> T:
    """return the last value from an iterable object

    ### Exceptions

    raises RuntimeError if the source yields no value
    """
    return next(last_gen(ensure_gen(source)))


def nth_gen(n: int, source: Yields[T]) -> Yields[T]:
    """yield the nth element yielded from a generator

    ### Exceptions

    raises `StopIteration` if `n` is greater than
    the number of values yielded from `source`

    ### Known Limitations

    Negative index values are not supported
    """
    s = abs(int(n))
    if s != n:
        raise TypeError("Unsupported index value", n)
    for idx in range(0, s):
        next(source)
    yield next(source)


def nth(n: int, source: Iterable[T]) -> T:
    """return the nth element from an iterable object

    ### Exceptions

    raises RuntimeError if `n` is greater than the
    number of values yielded from `source`

    ### Known Limitations

    Negative index values are not supported
    """
    return next(nth_gen(n, ensure_gen(source)))


T_k = TypeVar("T_k")
T_v = TypeVar("T_v")


def merge_map(source: Mapping[T_k, T_v],
              dest: Mapping[T_k, T_v],
              callback: Optional[Callable[
                  [T_k, T_v, Union[T_v, None], bool], T_v]] = None
              ):
    """merge a `source` mapping into a `dest`

    ### Usage

    `source`, `dest`
    : A `Mapping` object. The `dest`
    must not be immutable.

    `callback`
    : Optional function for merging values from the
    `source` mapping and, if present, from the `dest`
    mapping

    Returns the updated `dest_mapping`

    ### Overview

    `merge_map()` operates similar to `dict.update()`,
    with the following additional goals:
    - Ensure that any mapping values in the mapping
     `source` will be merged onto any corresponding
      mapping within the `dest` mapping.
    - Accept an optional callback for determing other
      values to be applied to the `dest` mapping.

    If a callback is provided, the callback must accept
    four positional args:
    - A key object from the `source` mapping.
    - The value for the key, from the `source` mapping.
    - The value for the hash-equivalent key from the `dest`
      mapping, or None if the `dest` mapping contains no value
      for that key.
    - A boolean flag, indicating whether the `dest` mapping
      contains a value for that key.

    The value returned from the callback will then be applied
    as the value for the hash-equivalent key in the `dest` mapping.

    If no callback is provided: Except for any common mapping
    values merged under the `source` and `dest` mappings, then
    similar to `dict.update()` the value from the `source` mapping
    will override.

    ### Known Limitations

    In all instances: For each mapping value in `source`,
    if a corresponding mapping exists for that key in
    `dest`,  then `merge_map()` will recursively merge
    the  mapping objects, given any provided callback.
    The mapping under `dest` will be modified in  the
    merge. If no  mapping exists for that key in `dest`,
    then the value returned from any `callback` would
    be applied to `dest`. If no callback is provided,
    the mapping from the `source` would be applied
    directly, without copy.

    If a callback is provided, the callback will be
    called for all Mapping objects from the `source`
    not  existing in `dest`, and for all non-mapping
    objects, whether or not common to `source` and
    `dest`. The callback may copy or re-use any values
    from the `source` and if available, from the `dest`
    mapping.

    If no callback is provided, this would not merge
    any non-mapping values for common keys of `source`
    and `dest`.  The value from the  `source`  would
    ovewrite the value for any hash-equivalent key
    in the `dest` mapping.

    In all instances:

    `merge_map()` assumes that all common mapping
    objects are mutable in the `dest` mapping.

    `merge_map()` will not detect any reference loop
    for values under the `source` mapping.
    """
    not_found = object()
    for key, value in source.items():
        dvalue = dest.get(key, not_found)
        if isinstance(value, Mapping) and dvalue is not not_found and isinstance(dvalue, Mapping):
            merge_map(value, dvalue, callback)
            continue
        if callback is None:
            dest[key] = value
        elif dvalue is not_found:
            dest[key] = callback(key, value, None, False)
        else:
            dest[key] = callback(key, value, dvalue, True)
    del not_found
    return dest


# autopep8: off
# fmt: off
__all__ = ["Yields",  "AsyncYields"]
export(__name__, ensure_gen, first_gen, first, last_gen, last, nth_gen, nth, merge_map)
