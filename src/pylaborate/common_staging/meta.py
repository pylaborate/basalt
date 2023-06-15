## meta.py - pylaborate.common_staging
'''utilities for metaprogramming'''

from collections.abc import Iterable
from typing import Sequence, Type
from .iterlib import Yields
from .naming import export


def merge_mro(bases: Sequence[Type]) -> Yields[Type]:
    '''utility for predicting a method resolution order

    ## Usage

    `merge_mro()` provides an estimate of the method resolution order
    for a class being initialized, given an unordered sequence of the
    class' base classes.

    Usage examples may include:

    - Given the set of base classes for a class providing a conventional
      method resolution order under `type.__new__()`: Ordered processing
      for annotations, attributes, and other qualities of each class
      that will be present within the class' method resolution order

    - Producing an ordered set of applicable classes for a polymorphic
      application of a given function `f(a)` with precedence determined
      per the method resolution order of the class of the parameter `a`,
      given an ordered set of classes for `a` as supported under the
      function's polymorphic definition.

    ## Known Limitations

    This function is believed to be consistent with the method
    resolution order of every defined class.
    '''
    ##
    found = []
    if __debug__ and not isinstance(bases, Iterable):
        raise AssertionError("Not an iterable value", bases)
    for cls in bases:
        for mrocls in cls.__mro__:
            if mrocls in found:
                found.remove(mrocls)
            found.append(mrocls)
    for cls in found:
        yield cls

# autopep8: off
# fmt: off
__all__ = []
export(__name__, merge_mro)  # NOQA: F405
