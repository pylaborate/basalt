## naming.py

"""utilities for management of bound names"""

import sys
from enum import Enum
from types import ModuleType
from typing import Any, Generator, List, Mapping, Optional, Sequence, Union
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


def _name_gen(v_all: Optional[Sequence], *objects) -> Generator[str, None, None]:
    ## local generator for object names
    ##
    ## v_all:
    ## : Either an existing __all__ attribute value from a module, or the
    ##   value None
    ##
    ## objects
    ## : sequence - string names, sequence values, or objects providing
    ##   a __name__ attribute. This will be processed as described for
    ##   `export`
    ##
    for o in objects:
        name = None
        if isinstance(o, str):
            name = o
        elif isinstance(o, Sequence):
            yield from _name_gen(v_all, *o)
        elif hasattr(o, "__name__"):
            name = o.__name__
        else:
            raise NameError(f"Unable to determine name for {o!r}", o)
        if name is not None:
            if (v_all is None) or (name not in v_all):
                yield name


def export(module: ModuleArg, obj, *objects) -> Sequence[str]:
    """export a sequence of attributes from a provided module

    ## Syntax

    `module`
    :   name of an existing module, or a module object

    `obj` and each element in `objects`
    :   objects for the export.
    :   For each string object, the value will be used as provided.
    :   For each sequence object, the object will be recursively
        processed as for `export`
    :   For each non-string, non-sequence object, the object
        must provide a `__name__` attribute

    ## Usage

    This function will set the `__all__` attribute on the
    denoted module by first extending the original `__all__`
    value, if found. If the module does not provide an
    `__all__` atribute at time of call, a new `__all__ value
    will be set on the module, in the form of a list.

    If the module uses a non-list `__all__` attribute, this
    function will endeavor to preserve the type of the original
    value. It's assumed that the type would provide a constructor
    accepting one argument, in the form of a list, representing
    the elements of the sequence of that type.

    ## Exceptions

    - raises `NameError` if `module` is not a module object and
      does not match the name of a module under `sys.modules`

    - raises `ValueError` if any non-string item in `objects`
      does not define a `__name__` attribute

    ## See Also

    - `export_enum()`
    - `export_annotated()`
    - `module_all()`

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

    export(__name__, 'datum', AClass, a_class)

    ```

    **Example:** high-order exports within a module's `__init__.py`

    This example exports a set of symbols imported from a relative `local`
    module.

    This assumes that the relative `local` module has defined an `__all__`
    atttribute.

    ```python
    from pylaborate.common_staging import export, module_all

    from .local import *
    export(__name__, module_all(__name__ + ".local"))
    ```

    """
    m = get_module(module)
    try:
        v_all = None
        if hasattr(m, "__all__"):
            v_all = m.__all__
            names = _name_gen(v_all, obj, *objects)
            if isinstance(v_all, List):
                v_all.extend(names)
            else:
                all_list = list(v_all)
                all_list.extend(names)
                v_all = v_all.__class__(all_list)
        else:
            v_all = list(_name_gen(None, obj, *objects))
        m.__all__ = v_all
        return v_all
    except NameError as exc:
        raise ValueError(f"Unable to export symbols from {m.__name__!s}", m) from exc


T = TypeVar("T")


def module_all(
    # fmt: off
    module: ModuleArg,
    default: Optional[T] = None
    # fmt: on
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


def bind_enum(enum: Enum, module: ModuleArg):
    """bind the member values of an enum class as constants within a module

    For each enum member field of the `enum`, with a field name of a
    form `<name>`, this function will bind an attribute `<name>` to the
    value of that `enum` field, within the denoted `module`.

    ## Implementation Notes

    - This function uses the value of each enum member field, for the
      top-level binding in the module

    See Also
    - `export_enum()`
    """
    ## may be useful for a @global_enum
    m = get_module(module)
    members = enum.__members__
    for name in members:
        item = members[name]
        setattr(m, name, item.value)


def export_enum(enum: Enum, module: ModuleArg) -> Sequence[str]:
    """bind and export the member values of an enum class within a module

    For each enum member field of the `enum`, with a field name of a
    form `<name>`, this function will bind an attribute `<name>` to the
    value of that `enum` field, within the denoted `module`.

    Lastly, this function will export each `<name>` and and the name of
    the `enum` class, within the `__all__` attribute of the denoted
    `module`

    ## Implementation Notes

    - If the module does not define an `__all__` attribute at time of
      call, a new `__all__` attribute will be initialized, of a type
      `List`

    - This function uses the value of each enum member field, for the
      top-level binding in the module

    ## See Also

    - `export()`
    - `bind_enum()`
    """
    m = get_module(module)
    bind_enum(enum, module)
    names = enum.__members__.keys()
    return export(m, enum.__name__, *names)


def export_annotated(module: ModuleArg) -> Optional[Sequence[str]]:
    '''export any annotated name from a module

    ## Usage

    For each `TypeAlias` name, or other annotation name defined in the
    denoted `module`, ensures that the name is present within the value
    of the `__all__` attribute of the module.

    ## See also

    - `export()`
    - `export_enum()`
    '''

    m = get_module(module)
    if hasattr(m, "__annotations__"):
        return export(m, tuple(m.__annotations__.keys()))


def origin_name(object) -> str:
    if hasattr(object, "__name__"):
        name = object.__name__
        prefix = None
        if hasattr(object, "__module__"):
            m = object.__module__
            if m != 'builtins':
                prefix = origin_name(get_module(m))
        if prefix:
            return prefix + "." + name
        else:
            return name
    else:
        raise ValueError("Object does not provide a __name__: %s" % repr(object), object)

def get_object(name: str, context: Any = sys.modules) -> Any:
    ## tentative utility function
    _context = context
    if isinstance(context, str):
        _context = get_module(context)
    data = name.split(".", 1)
    n_data = len(data)
    if n_data is int(0):
        raise ValueError("Uncrecognized object name: %s" % repr(name), name)
    elif n_data is int(1):
        if isinstance(context, Mapping):
            return _context.get(name)
        else:
            return getattr(_context, name)
    else:
        next_context = get_object(data[0], _context)
        return get_object(data[1], next_context)


# autopep8: off
# fmt: off
export(__name__,
       NameError, 'ModuleArg', get_module, export, module_all,
       bind_enum, export_enum, origin_name, get_object
       )
