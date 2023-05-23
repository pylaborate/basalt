# utility forms for collections and sequences

from .naming import export
from typing import Any, List, Callable, Collection, Generator, Hashable, TypeVar

H = TypeVar('H', bound=Hashable)


def uniq(col: List[H],
         hash_call: Callable[[H], Any] = hash,
         reverse: bool = True) -> List[H]:
    '''
    Unique in-place processor for mutable lists of hashable values.

    This function modifies the input value in place, removing non-unique values.
    The processed collection will be returned.

    The provided `hash_call` function should be callable for each element in the
    provided collection. The function should return a unique value for each unique
    element in the collection.

    If `reverse` provides a non-falsey value, then any non-unique elements will be
    removed as starting from the end of the provided collection. This procedure may
    avoid a small number of addition/subtration calls, and thus has been implemented
    as the default.

    Caveats:

    The provided collection `col` must implement an indexed `pop` method, with a
    signature `col.pop(n: int).`
    '''
    colen = len(col)
    if len == 0:
        return col
    buf = list()
    start = colen if reverse else 0
    end = 0 if reverse else colen
    count = -1 if reverse else 1
    nremoved = 0
    for n in range(start, end, count):
        # shift for Python range semantics in reverse traversal,
        # shift for index after duplicate removal in forward traversal
        idx = n - 1 if reverse else n - nremoved
        v = col[idx]
        h = hash_call(v)
        if h in buf:
            col.pop(idx)
            if not reverse:
                nremoved = nremoved + 1
        else:
            buf.append(h)
    return col


def uniq_gen(col: Collection[H],
             hash_call: Callable[[H], Any] = hash) -> Generator[H, None, None]:
    '''
    Unique generator for mutable and immutable collections of hashable values.

    The provided `hash_call` function should be callable for each element in the
    provided collection. The function should return a unique value for each unique
    element in the collection.

    For each element in the collection for which the `hash_call` returns a unique value,
    the generator will yield that element to the caller.
    '''
    buf = []
    for elt in col:
        h = hash_call(elt)
        if h not in buf:
            yield elt
            buf.append(h)


# autopep8: off
# fmt: off
__all__ = []
export(__name__, __all__, uniq, uniq_gen)
