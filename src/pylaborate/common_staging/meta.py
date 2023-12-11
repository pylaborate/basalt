'''utilities for metaprogramming'''

from collections.abc import Iterable
from .iterlib import Yields
from .naming import export


def merge_mro(bases: Iterable[type]) -> Yields[type]:
    '''utility for predicting a method resolution order

    ## Usage

    `merge_mro()` provides an estimate of the method resolution order
    for a class being initialized, given an unordered sequence of the
    class' base classes.

    Usage Examples / Design Notes:

    - Given the set of base classes for a class providing a conventional
      method resolution order under `type.__new__()`: `merge_mro()` may
      be applied for an ordered processing in definitions of annotations,
      attributes, and other qualities of each class in the eventual MRO
      for a new class

    - Producing an ordered set of applicable classes for a polymorphic
      application of a function `f(a)` with precedence determined
      per the method resolution order of the class of the value `a`,
      beginning with an ordered set of the base classes for the class `a`

    ## Known Limitations

    This function is believed to be consistent with the method
    resolution order for conventional Python type definitions,
    vis a vis type.mro()
    '''
    ##
    found = []
    for cls in bases:
        for mrocls in cls.__mro__:
            if mrocls in found:
                found.remove(mrocls)
            found.append(mrocls)
    yield from found

# autopep8: off
# fmt: off
__all__ = []
export(__name__, merge_mro)  # NOQA: F405
