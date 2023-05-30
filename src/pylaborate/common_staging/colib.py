## colib.py

"""utilities for collections and sequences"""

from .naming import export
from typing import Any, List, Callable, Collection, Generator, Hashable, TypeVar

H = TypeVar("H", bound=Hashable)


def uniq(
    col: List[H], hash_call: Callable[[H], Any] = hash, reverse: bool = True
) -> List[H]:
    """
    Unique in-place processor for lists of hashable values.

    ## Usage

    This function modifies the input `col` in place, removing non-unique values.
    The processed list will be returned.

    The provided `hash_call` function should be callable for each element in the
    list. The function should return a unique value for each unique list element.

    If `reverse` provides a non-falsey value, non-unique elements will be removed as
    starting from the end of the provided list. This approach may avoid a small number
    of additional calls in the implementation, and has been selected as a default.

    ## Implementation Notes

    - The type signature for this function has specified that the input value should be
      a list. As a minimum, the `col` must support an indexed form of object reference
      and a `pop` method, with a type signature `col.pop(n:int)`
    """
    colen = len(col)
    if len == 0:
        return col
    buf = []
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


def uniq_gen(
    col: Collection[H], hash_call: Callable[[H], Any] = hash
) -> Generator[H, None, None]:
    """
    Unique generator for collections of hashable values.

    ## Usage

    The provided `hash_call` function should be callable for each element in the
    provided collection. The function should return a unique value for each unique
    element in the collection.

    For each element in the collection for which the `hash_call` returns a unique
    value, the generator will yield the element to the caller.
    """
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
