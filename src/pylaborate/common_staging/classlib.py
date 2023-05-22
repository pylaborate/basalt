
from .funlib import export
from enum import IntFlag
from typing import Callable, Literal, Optional, Type

class ContextManager:
    '''Utility class for defininig context manager implementations.

    This class defines a rudimentary implementation for each of the
    `__enter__` and `__exit__` methods. The `__enter__` method
    defined by this class will return the instance from the method.

    See also:
    - Python 3 Documentation: [contextlib — Utilities for with-statement contexts](https://docs.python.org/3/library/contextlib.html)

    **Example:**

    The following example defines an `__enter__` method, overriding the
    `__enter__` method defined within the class, ContextManager. The context
    manager is then applied for a purpose of listing all non-constructor methods
    defined within the `bultins` module.

    ```python
    import re
    import sys
    from typing import Callable, Type

    class ModuleContextManager(ContextManager):
        """context manager for reflection on module objects"""
        def __init__(self, name: str):
            mod = sys.modules.get(name, None)
            if mod is None:
                raise RuntimeError("Module not found: " + repr(name), name)
            else:
                self._module = mod

        def __enter__(self):
            return self._module

    with ModuleContextManager("builtins") as mod:
        name = mod.__name__
        print("Visible Methods (Not Constructors) in `%s`:" % name)
        found = False
        for attr in dir(mod):
            if len(attr) == 0 or attr[0] == "_":
                continue
            obj = getattr(mod, attr)
            if isinstance(obj, Callable) and not isinstance(obj, Type):
                if not found:
                    found = True
                doc = getattr(obj, '__doc__', None)
                if doc:
                    print("  " + attr + ":\\t" + re.split("[\\n\\r]+", doc, maxsplit = 1)[0])
                else:
                    print("  " + attr)
        if not found:
            print("  (None)")
    ```
    '''
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class MethodRecurseKind(IntFlag):
    RECURSE_NONE = 0
    RECURSE_INSTANCE = 1
    RECURSE_CLASS = 2


def find_function(base: object, name: str, omit_constructors: bool = False,
                  recurse: Optional[MethodRecurseKind | bool] = False,
                  error: Optional[bool | Type | Callable] = RuntimeError) -> Optional[Callable | Literal[False]]:
    found = None
    if hasattr(base, name):
        attr = getattr(base, name)
        if (isinstance(attr, Callable) and (not isinstance(attr, Type)) if omit_constructors else True):
            found = attr
    elif recurse:
        sources = []
        if (recurse & MethodRecurseKind.RECURSE_INSTANCE) != 0:
            sources.extend(base.__class__.__bases__)
        if (recurse & MethodRecurseKind.RECURSE_CLASS) != 0:
            sources.extend(base.__class__)
        for cls in sources:
            found = find_function(cls, name, recurse = recurse, error = False, omit_constructors=omit_constructors)
            if found:
                break
    if found:
        return found
    else:
        if error:
            _error = error
            if error is True:
                _error = RuntimeError
            if isinstance(_error, Type):
                ## assuming `error` is an exception class
                extra = " (Constructors Ommitted)" if omit_constructors else ""
                raise _error("Function not found: %r in %r" % (name, base,) + extra, base, name)
            else:
                ## assuming `error` is callable
                _error(base, name)
            # does not return. type checkers might not recognize this ...
            return
        else:
            return False

## FIXME inline tests
# print(find_function(sys.modules['builtins'], 'tuple'))
# print(find_function(sys.modules['builtins'], 'tuple', omit_constructors = True))


# autopep8: off
# fmt: off
__all__ = []
export(__name__, __all__, ContextManager)
