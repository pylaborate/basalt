## naming.py

'''utilities for management of bound names'''

import sys
from types import ModuleType
from typing import Generator, List, Optional, Sequence, Union
from typing_extensions import Annotated, TypeAlias, TypeVar


class NameError(LookupError):
    """Exception class for `LookupError` generalized to an object name"""

    pass


ModuleArg: Annotated[TypeAlias, "Module or module name"] = Union[str, ModuleType]


def get_module(ident: ModuleArg) -> ModuleType:
    """conditional accessor for `sys.modules`

    ## Usage

    If `ident` denotes a module, returns that module.

    If `ident` is a string identifying a module in `sys.modules`,
    returns the named module.

    ## Exceptions

    - Raises `NameError` if `ident` is a string that does not
      identify a module in `sys.modules`.
    """
    if isinstance(ident, str):
        if ident in sys.modules:
            return sys.modules[ident]
        else:
            raise NameError(f"Module not found for name: {ident!r}", ident)
    else:
        return ident


def _name_gen(*objects) -> Generator[str, None, None]:
    ## local generator for object names
    for o in objects:
        if isinstance(o, str):
            yield o
        elif isinstance(o, Sequence):
            yield from _name_gen(*o)
        elif hasattr(o, "__name__"):
            yield o.__name__
        else:
            raise NameError(f"Unable to determine name for {o!r}", o)


def export(
    module: ModuleArg, cache: List[str], obj, *objects
) -> List[str]:
    """export a list of attributes from a provided module

    ## Syntax

    `module`
     :   name of an existing module, or a module object

    `cache`
     :   intermediate storage for the export. This value  will be
        destructively modified with `all.extend()` then set as the
        value of the `__all__` attribute for the module.

    `obj` and each element in `objects`
     :   objects for the export.
     :   For each string, the value will  be used as provided.
     :   For each sequence object, the object will be recursively
          processed as for `export`
     :   For each non-string and non-sequence object, the object
          must provide a `__name__` attribute

    ## Usage

    This function will set the `__all__` attribute on the
    denoted module by first extending the provided `all`
    value then setting the module's `__all__` attribute to
    that value.

    If the module's existing `__all__` value should be extended,
    the value may be provided as the `all` parameter value.

    ## Exceptions

    - raises `NameError` if `module` is not a module object and
      does not match the name of a module under `sys.modules`

    - raises `ValueError` if any non-string item in `objects`
      does not define a `__name__` attribute

    - raises `TypeError` if the `cache` value is not a list

    ## Examples

    **Example:** re/initializing a module's `__all__` attribute
    ```python
    from pylaborate.common_staging import export
    from typing import Union
    from typing_extensions import TypeAlias

    ## variables must be exported by string name
    datum: TypeAlias = Union[str, int]

    class AClass():
        pass

    def a_class():
        return AClass

    __all__ = []
    export(__name__, __all__, 'datum', AClass, a_class)

    ```

    **Example:** high-order exports within a module's `__init__.py`

    This example exports a set of symbols imported from a relative `local`
    module.

    This assumes that the relative `local` module has defined an `__all__`
    atttribute.

    ```python
    from pylaborate.common_staging import export, module_all

    from .local import *
    export(__name__, __all__, module_all(__name__ + ".local"))
    ```

    """
    m = get_module(module)
    if not isinstance(cache, List):
        raise TypeError(f"In export for {m!r}, not a list: {cache!r}", m, cache)
    try:
        # fmt: off
        ext = _name_gen(obj, *objects)
        # fmt: on
        cache.extend(ext)
    except NameError as exc:
        raise ValueError(f"Unable to export symbols from {m!r}", m) from exc
    ## using setattr, this may avoid a spurious type-check warning here:
    setattr(m, "__all__", cache)
    return cache


T = TypeVar("T")


def module_all(
    module: ModuleArg, default: Optional[T] = None
) -> Optional[Union[List[str], T]]:
    """retrieve the value of the `__all__` attribute of a module, if defined.

    If the module does not define an `__all__` attribute, returns the
    `default` value.

    ## Syntax

    `module`:
        name of an existing module, or a module object

    `default`:
        value to be returned if the module does not define an `__all__`
        attribute

    ## Exceptions

    - raises `NameError` if `module` is not a module object and
      does not match the name of a module under `sys.modules`
    """
    _m = get_module(module)
    if hasattr(_m, "__all__"):
        return _m.__all__
    else:
        return default


# autopep8: off
# fmt: off
__all__ = []  # type: ignore
export(__name__, __all__,
       NameError, 'ModuleArg', get_module, export, module_all
       )
