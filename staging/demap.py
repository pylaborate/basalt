## demap - pylaborate

from collections import deque

# from dataclasses import dataclass
from itertools import chain
import os
from pathlib import Path
import shlex
from typing import Any, Generic, Optional, Union
from typing_extensions import Self, TypeAlias, TypeVar
from collections.abc import Callable, Generator, Iterable, Sequence, Mapping

T = TypeVar("T")


class DemapEntry(Generic[T]):
    """key and value storage for `Demap`"""

    @property
    def key(self) -> str:
        return self._key

    @key.setter
    def key(self, new_value: str):
        # fmt: off
        raise TypeError("Operation not supporteed: set key value in an initialized %s",
                        self.__class__.__name__)
        # fmt: on

    @property
    def keyhash(self) -> int:
        return self._keyhash

    @keyhash.setter
    def keyhash(self, new_value: int):
        # fmt: off
        raise TypeError("Operationt not supported: set keyhash value in an initialized %s",
                        self.__class__.__name__)
        # fmt: on

    @property
    def value(self) -> T:
        return self._value

    @value.setter
    def value(self, new_value: T):
        self._value = new_value

    def __init__(self, key: str, value: T):
        self._key = key
        self._keyhash = hash(key)
        self._value = value

    def __repr__(self):
        # fmt: off
        return "<%s at 0x%x %s = %s>" % (self.__class__.__name__, id(self),
                                         self.key, repr(self.value))
        # fmt: on

    def __str__(self):
        return "%s(%r, %s)" % (self.__class__.__name__, self.key, repr(self.value))


class Demap(Mapping[str, T]):
    """Mapping type based on a `deque`"""

    def __init__(
        self,
        initial: Optional[Union[Mapping[str, T], Sequence[Sequence[str, T]]]] = None,
    ):
        initial_items = [False] * len(initial) if initial else ()
        n = 0
        if isinstance(initial, Mapping):
            for key in initial:
                initial_items[n] = DemapEntry(key, initial[key])
                n = n + 1
        elif isinstance(initial, Sequence):
            for key, value in initial:
                initial_items[n] = DemapEntry(key, value)
                n = n + 1
        self._que = deque(initial_items)

    def __copy__(self):
        q = self._que
        cache = [[False, False]] * len(q)
        n = 0
        for item in q:
            nth = cache[n]
            nth[0] = item.key()
            nth[1] = item.value()
        return self.__class__(cache)

    def copy(self):
        return self.__copy__()

    def update(self, mapping):
        if isinstance(mapping, Mapping):
            for key in mapping:
                self[key] = mapping[key]
        elif isinstance(mapping, Sequence):
            for key, value in mapping:
                self[key] = value

    def __missing__(self, key: str):
        raise KeyError("Key not found", key, self)

    def __contains__(self, key: str):
        try:
            self.__getitem__(key)
            return True
        except KeyError:
            return False

    def _each_queued(self, key: str):
        ## reusable iterator for __getitem__ and __setitem__
        h = hash(key)
        q = self._que
        for item in q:
            if item.keyhash == h:
                yield item

    def __getitem__(self, key: Union[str, int]) -> T:
        for first in self._each_queued(key):
            return first.value
        self.__missing__(key)

    def __setitem__(self, key: str, value: T):
        for first in self._each_queued(key):
            first.value = value
            return
        ## not found:
        self._que.append(DemapEntry(key, value))

    def __delitem__(self, key: str):
        try:
            item = self.__getitem__(key)
            self._que.remove(item)
            return True
        except KeyError:
            return False

    def pop(self, key: str) -> T:
        self.__delitem__(key)

    def __iter__(self):
        for item in self._que:
            yield item.key

    def __len__(self):
        len(self._que)

    def __str__(self):
        keys = (item.key for item in self._que)
        return "%s(%s)" % (self.__class__.__qualname__, ", ".join(keys))

    def __repr__(self):
        keys = (item.key for item in self._que)
        # fmt: off
        return "<%s at 0x%x (%s)>" % (self.__class__.__qualname__, id(self),
                                      ", ".join(keys))
        # fmt: on


## FIXME: Extend Demap for concurrent applications:
## - acquire a lock before each dispatch to super()
## - SyncDemap, using a threading lock
## - AsyncDemap, using an aio lock
## - implement tests


##
## MkVars extension onto Demap
##


# fmt: off
MkVarsMap: TypeAlias = Union[Mapping[str, "MkVarsSource"], "MkVars"]

MkVarsSource: TypeAlias = Union[
    str, MkVarsMap, Iterable["MkVarsSource"], Sequence["MkVarsSource"],
    Callable[[], "MkVarsSource"]
]
# fmt: on

# class MkVarsEntry(DemapEntry):
#     callback: Callable[[], "MkVarsSource"]


class MkVars(Demap[T]):
    """Mapping type for macro-like expansion of formatted string values"""

    def __getattr__(self, name: str):
        """Implementation for attribute-based reference to the mapping table of this MkVars"""
        try:
            return self.__getitem__(name)
        except KeyError:
            ## TBD dispatch under os.environ
            raise AttributeError("Attribute not found", name, self)

    def parse(
        # fmt: off
        self, obj: MkVarsSource, kwargs: Optional[MkVarsMap] = None,
        yield_items=False, genexpand: Callable[[Iterable], Any] = tuple
        # fmt: on
    ):
        """Process a `MkVarsSource` value for expansions from callbacks and `str.format()`.

        If `kwargs` is None, `parse()` will use the mapping provided in
        the calling MkVars object.

        In the generator returned by this function, the semantics of
        the generator's `yield` behaviors will differ as per the type of
        the `obj`.

        - For a string `obj`, the result of `obj.format(**kwargs)` will
          be yielded.

        - For a path `obj`, the string representation of the of object
          will be yielded, with user homedir expansion

        - For a generator `obj`, each value yielded from the generator
          will be processed with `parse()`. The sequence of processed
          values will be provided in the format of a `chain` iterator
          to the function provided as `genexpand`. The value returned
          by the `genexpand` function will be the value yielded in this
          instance.

          The default behavior is to yield a tuple containing a sequence
          of processed values, after values yielded by a generator `obj`.

        - For a sequence `obj`, each element will be processed as with
          `parse,` then added to an ephemeral list. The list will be
          provided to a constructor function using the class of the
          `obj`. The new sequence object will be yielded.

        - For a callable `obj`, the `obj` will be called with no
          arguments, then the return value processed as with
          `parse()` and the processed value yielded.

        - For a mapping-typed `obj` in a top-level call to `parse()`,
          the yield behavior will differ as per the value provided for
          `yield_items`.

          If `yield_items` is provided as `True` or a _truthy_ value
          within a top-level call to `parse`, each key and processed
          value pair will be yielded to the caller, within a tuple. This
          may allow for the caller to ensure that any values are updated
          in the containing MkVars, during processing.

          Otherwise, and for all nested mappings under `obj`, the
          handling is similar to the `sequence` case.

          If `yield_items` is a _falsey_ value, a new mapping will be
          constructed of the same type as the  `obj` mapping. The
          object's constructor will be provided with an ephemeral
          dictionary of keys and processed values, then the new mapping
          object will be yielded.

        - For all other types of `obj`, the original `obj` will be
          yielded.

        ## Implementation Notes

        **Assumptions**

        For a top-level call to `parse` onto a mapping `obj`, the
        `yield_items` arg should generally be provided with a value
        `True`. This will ensure that the generator will yield each
        successive key and processed value, expanded as per the
        semantics denoted above.

        For a sequence type object or a mapping object, it's assumed
        that the constructor for the object's class will accept an
        initial value in a format generally similar to the original
        object, namely a List arg for a sequence constructor or a Dict
        arg for a constructor onto a nested mapping.

        The `genexpand` function is assumed to accept a single literal
        argument. This object will be provided in the form of an
        iterable `chain` object. The value returned by the `genexpand`
        function will be yielded as the processed result for any
        generator value, in the expansion of the call to `parse()`. As
        denoted above, the default behavior is to yield a tuple
        expansion for all elements yielded from a generator.

        It's assumed that all callback functions and constructors for
        values provided under `kwargs` will not modify the state of the
        processing environment. Limited under this assumption, `parse()`
        is a generally reentrant function.

        **Deferred Attribute References**

        A callable value may be provided within `kwargs`, such as to
        defer any reference to an object's attributes during source
        evaluation. This may be of use when a referenced attribute may
        not have been bound at the time when the expression is evaluated
        -- e.g if referencing the value of a MkVars binding `obj[key]`
        as `obj.key`, while the 'key' binding would not have been
        established within the environment of the source evaluation.

        In this instance, generally the calling expression may be
        wrapped within an anonymous lambda or other callable, then the
        callback provided in place of the original value expression.

        **Alternative Call Semantics**

        A higher-order interface for `parse()` is available in the
        each of the `setvars()` and `dup()` methods. These methods each
        provide an interface for evaluation of key values within the
        calling MkVars.

        **Design**

        This function was designed after the semantics of string value
        expansion for Makefile expressions. This design has been adapted
        to accomodate a subset of object types available in Python 3.
        """
        ##
        ## Generator for expanding a MkVars source value
        ##
        if kwargs is None:
            kwargs = self
        match obj:
            # fmt: off
            case str():
                yield obj.format(**kwargs)
            case Path():
                yield str(obj.expanduser())
            case Generator():
                yield genexpand(chain.from_iterable(self.parse(elt, kwargs) for elt in obj))
            case Sequence():
                n_elts = len(obj)
                elts = [False] * n_elts
                n = 0
                for item in obj:
                    for newmap in self.parse(item, kwargs):
                        elts[n] = newmap
                    n = n + 1
                yield obj.__class__(elts)
            case Mapping():
                n = 0
                if not yield_items:
                    newmap = dict()
                for k in obj:
                    for expansion in self.parse(obj[k], kwargs):
                        if yield_items:
                            ## yield the key and new binding, such that the caller
                            ## can update the containing object and kwargs map
                            yield (k, expansion,)
                        else:
                            newmap[k] = expansion
                            n = n + 1
                if not yield_items:
                    yield obj.__class__(newmap)
            case Callable():
                yield from self.parse(obj(), kwargs)
            case _:
                yield obj
            # fmt: on

    def setvars(self, **kwargs):
        """process and update this MkVars mapping, with string expansion

        `setvars()` provides an interface onto `parse()`, such that the
        calling MkVars object will be successively updated for value
        expansion, given each successive value yielded from `parse()`,
        for each key and value pair defined in the calling MkVars object.

        Values provided in `kwargs` will in effect override any values
        defined in the calling MkVars object, for string keyword
        expansion during the call to `parse()`

        ## See also

        - `parse()`
        - `dup()

        ## Known Limitations

        This function will modify values in the MkVars mapping of the
        calling object, for each successive key and each processed
        value yielded in the call to `parse()`.

        This is not a reentrant function. If the parsing fails for any
        binding in `kwargs`, it should be assumed that the original
        MkVars mapping may not have been completely dereferenced.
        """

        ## pre-initialize values in the mock mapping, for variable expansion
        mock = self.copy()
        ## apply all kwargs to the mock. This object will be used as an
        ## ephemeral mapping in the call to parse()
        mock.update(kwargs)
        ## update the mapping in the calling object and in the kwargs source
        for attr, value in self.parse(kwargs, mock, True):
            mock[attr] = value
            self[attr] = value

    def dup(self, **kwargs) -> Self:
        """return a copy of this MkVars, updated with string expansion per `kwargs`

        This function provides an alternative to `setvars()` as an
        interface onto `parse()` not modifying the calling MkVars
        object.

        The `dup()` method will return a new MkVars instance, representing
        a copy of the calling instance modified with value expansion as
        under `parse()`.

        The MkVars copy will be initially updated for the mapping in
        `kwargs`. The updated copy will then provided as the `kwargs`
        value to `parse(). The updated copy will then be returned.

        ## Known Limitations

        This function may provide limited support for deferred reference
        through callbacks onto the containing MkVars object. As with
        `parse()`, any string references will be expanded using
        `str.format()`, given the keyord mapping under the newly
        initialized MkVars copy.

        The return values for any callback functions within the mvkars
        mapping may be reflective of the stack environment of the
        calling object, rather than the newly initialized object copy.
        """
        mock = self.copy()
        mock.update(kwargs)
        for attr, value in self.parse(kwargs, mock, True):
            mock[attr] = value
        return mock

    def value(self, source: MkVarsSource, genexpand: Callable[[Iterable], Any] = tuple):
        # return source.format(**self)
        for item in self.parse(source, self, genexpand=genexpand):
            return item

    def cmd(self, source: Union[str, Callable[[], str]]):
        return shlex.split(self.value(source))


##
## Tests
##

import sys


def optional_files(*files: Sequence[str]) -> Generator[str, None, None]:
    for pathname in files:
        if os.path.exists(pathname):
            yield pathname


def get_venv_bindir(venv_dir: str) -> str:
    ## from project.py
    ##
    ## Return an effective guess about the location of the scripts or 'bin'
    ## subdirectory of the provided venv_dir.
    ##
    ## This assumes that all Python virtual environment providers would use
    ## essentially the same scripts subdirectory name - possibly differing
    ## in character case, on operating systems utilizing a case-folding
    ## syntax in filesystem pathnames
    ##
    ## referenced onto venv ___init__.py, Python 3.9
    if sys.platform == "win32":
        return os.path.join(venv_dir, "Scripts")
    else:
        return os.path.join(venv_dir, "bin")


def run_test():
    mkv = MkVars()
    mkv.setvars(
        build_dir="build",
        stampdir="{build_dir}/.build_stamp",
        host_python="python3",
        venv_dir="env",
        env_cfg="{venv_dir}/pyvenv.cfg",
        pyproject_cfg="pyproject.toml",
        # fmt: off
        requirements_in=optional_files("requirements.in"),
        requirements_local=optional_files("requirements.local"),
        # requirements_nop: test case - value source, generator => empty tuple
        requirements_nop=optional_files("/nonexistent/requirements.txt"),
        requirements_txt="requirements.txt",
        requirements_depends=lambda: (mkv.pyproject_cfg, *mkv.requirements_nop, *mkv.requirements_in, *mkv.requirements_local,),
        # fmt: on
        project_py="project.py",
        pyproject_extras=("dev",),
        homedir=os.path.expanduser("~"),
        pip_cache="{homedir}/.cache/pip",
        ## beta tests for mkvars (FIXME move to test dirs)
        beta_dct=dict(a="{pip_cache}", b="{project_py}"),
        beta_int=51,
        pip_options="--no-build-isolation -v --cache-dir={pip_cache!r}",
        # fmt: off
        opt_extras=lambda: " ".join("--extra {opt}".format(opt = opt) for opt in mkv.pyproject_extras),
        pip_compile_options='--cache-dir={pip_cache!r} --resolver=backtracking -v --pip-args {pip_options!r} {opt_extras}',
        # fmt: on
        pip_sync_options="-v --ask --pip-args {pip_options!r}",
        env_bindir=lambda: get_venv_bindir(mkv.venv_dir),
        env_pip="{env_bindir}/pip",
        env_pip_compile="{env_bindir}/pip-compile",
        pip_compile_depends=lambda: ("{env_pip_compile}", *mkv.requirements_depends),
        home_path=Path("~"),
    )

    return mkv
