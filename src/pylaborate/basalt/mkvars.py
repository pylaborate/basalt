## mkvars - pylaborate.basalt
"""String macro expansion for Python, in a Make-like syntax"""

from collections import UserDict
from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
import dataclasses as dc

# from itertools import chain
import itertools
import logging
import logging.config
from numbers import Number
import os
from pathlib import Path
from pylaborate.common_staging import merge_mro, merge_map, get_logger, LogLevel
import shlex
import sys
## type hints
from types import MappingProxyType
from typing import Any, Generic, Optional, Union, Type
from typing_extensions import Self, TypeAlias, TypeVar


##
## Types
##

# fmt: off

MkVarsMap: TypeAlias = Mapping[str, "MkVarsSource"]


MkVarsSource: TypeAlias = Union[
    str, Number, Path, MkVarsMap, Sequence["MkVarsSource"], Callable[[], "MkVarsSource"]
]

MkVarsSourceMap: TypeAlias = Mapping[str, MkVarsSource]

MkVarsValue: TypeAlias = Union[
    str, Number, Mapping[str, "MkVarsValue"], Sequence["MkVarsValue"]
]

Ts = TypeVar('Ts', bound=MkVarsSource)
Tv = TypeVar('Tv')

# fmt: on

##
## Formatting Protocol for MkVars
##


@dataclass(repr=False, order=False)
class MkFormatter(Generic[Ts, Tv]):
    key: str
    source: Ts
    mapping: "MkVars"
    expansion: Optional[Tv] = None


    @property
    def value_class(self) -> Type:
        if hasattr(self, "_value_class"):
            return self._value_class
        else:
            cls = self.source.__class__
            self._value_class = cls
            return cls

    @value_class.setter
    def value_class(self, cls: Type):
        self._value_class = cls

    def key_for(self, value):
        if __debug__:
            ## return an informative key value, for debug purposes
            ##
            ## called when initializing a new MkFormatter for formatting
            ## some value under the source of the calling MkFormatter
            sk = self.key
            # fmt: off
            vcls = value.__class__.__name__
            vtag = "%s_0x%x" % (vcls, id(value),)
            if sk is None:
                scls = self.source_class().__name__
                tag = "%s_0x%x" % (scls, id(self),)
                return (tag, vtag,)
            elif isinstance(sk, str):
                return (sk, vtag,)
            elif isinstance(sk, Iterable):
                return (*sk, vtag,)
            else:
                return None
            # fmt: on

    @property
    def key_str(self):
        sk = self.key
        if isinstance(sk, str):
            return sk
        elif isinstance(sk, Sequence):
            ## this assumes a sequence of strings
            return "(" + ", ".join(sk) + ")"
        else:
            return repr(sk)

    def __repr__(self):
        # fmt: off
        return "<%s at 0x%x %s>" % (self.__class__.__qualname__, id(self), self.key_str)
        # fmt: on

    def __str__(self):
        return repr(self)

    def expand(self, kwargs=None) -> Tv:
        ## method will be overridden in subclasses
        return self.source

    @classmethod
    def source_class(cls) -> Type[object]:
        return object

    def parse(self, kwargs=None) -> MkVarsValue:
        self.log_debug("MKFORMATTER PARSE @ %s : %s", self.key, repr(self.source))
        expansion = self.expansion
        if expansion and not self.mapping.evaluate:
            self.log_trace("MKFORMATTER CACHED %s", repr(expansion))
            return expansion
        else:
            source = self.source
            expansion = self.expand(source)
            self.expansion = expansion
            self.log_trace("MKFORMATTER PARSED %s", repr(expansion))
            return expansion

    def update(self, source: MkVarsSource):
        self.source = source
        self.expansion = None

    def reset(self):
        self.log_trace("RESET")
        self.expansion = None

    def log_debug(self, message, *args):
        self.mapping.log_debug(
            "%s %s: " + message, self.__class__.__name__, self.key, *args
        )

    def log_trace(self, message, *args):
        self.mapping.log_trace(
            "%s %s: " + message, self.__class__.__name__, self.key, *args
        )

    def __iter__(self):
        source = self.source
        if isinstance(source, Iterable):
            yield from self.source
        else:
            raise TypeError("Not an iterable source", source, self)

    def __len__(self):
        source = self.source
        if isinstance(source, Iterable):
            return len(source)
        else:
            raise TypeError("Not an iterable source", source, self)

    def __copy__(self):
        cp = dc.replace(self)
        cp.reset()
        return cp

    def copy(self):
        return self.__copy__()


S = TypeVar("S")


@dataclass(repr=False, order=False)
class StrFormatter(MkFormatter[S, str], Generic[S]):
    @classmethod
    def source_class(cls) -> Type[str]:
        return str

    def expand(self, overrides: Optional[MkVarsSourceMap] = None) -> str:
        usemap = self.mapping
        return self.source.format_map(usemap)


@dataclass(repr=False, order=False)
class PathFormatter(StrFormatter[Path]):
    @classmethod
    def source_class(cls) -> Type[Path]:
        return Path

    def expand(self, overrides: MkVarsSourceMap) -> str:
        ## format the string representation of the pathname
        s = str(self.source)
        return s.format_map(self.mapping)


@dataclass(repr=False, order=False)
class VolatileFormatter(MkFormatter[Ts, Tv]):
    _volatile: Optional[Tv] = None
    _is_cached: bool = False

    def get_cached_value(self):
        if self._is_cached:
            cached = self._volatile
        else:
            cached = self.wrap_volatile()
            self._volatile = cached
            self._is_cached = True
        return cached

    def expand(self, _) -> Tv:
        return self.mapping.parse(self.get_cached_value())

    def reset(self):
        super().reset()
        if self._is_cached:
            cached = self._volatile
            if isinstance(cached, MkFormatter):
                self.log_trace("RESET CACHED")
                cached.reset()

@dataclass(repr=False, order=False)
class MapFormatter(VolatileFormatter[Mapping[str, Ts], Mapping[str, Tv]]):
    @classmethod
    def source_class(cls) -> Type[Mapping]:
        return Mapping

    def wrap_volatile(self):
        assert self._volatile is None, "wrap_volatile called over a cached value"
        source = self.source
        mapping = self.mapping
        fmap = dict()
        for k, v in source.items():
            formatter = mapping.ensure_formatter(v, self.key_for(v))
            fmap[k] = formatter
        return fmap

    def expand(self, _):
        formatted = self.get_cached_value()
        mapping = self.mapping
        newmap = dict()
        for k, v in formatted.items():
            expansion = mapping.parse(v)
            newmap[k] = expansion
        cls = self.value_class
        return cls(newmap)


@dataclass(repr=False, order=False)
class SeqFormatter(VolatileFormatter[Sequence[Ts], Sequence[Tv]]):
    @classmethod
    def source_class(cls) -> Type[Sequence]:
        return Sequence

    def wrap_volatile(
        self, overrides: Optional[MkVarsSourceMap] = None
    ) -> Sequence[Tv]:
        assert self._volatile is None, "wrap_volatile called over a cached value"
        source = self.source
        mapping = self.mapping
        n_elts = len(source)
        formatters = [False] * n_elts
        n = 0
        for elt in source:
            formatters[n] = mapping.ensure_formatter(elt, self.key_for(elt))
            n = n + 1
        return formatters

    def expand(self, unused) -> Tv:
        formatters = self.get_cached_value()
        mapping = self.mapping
        n_elts = len(formatters)
        elts = [False] * n_elts
        for n in range(0, n_elts):
            elts[n] = mapping.parse(formatters[n])
        cls = self.value_class
        return cls(elts)


@dataclass(repr=False, order=False)
class CallableFormatter(VolatileFormatter[Callable[[Ts], Tv], Tv]):
    @classmethod
    def source_class(cls) -> Type[Callable]:
        return Callable

    def wrap_volatile(self) -> Tv:
        assert self._volatile is None, "wrap_volatile called over a cached value"
        v = self.source()
        self.log_trace("VOLATILE %s", v)
        wrap = self.mapping.ensure_formatter(v, self.key_for(v))
        self.log_trace("VOLATILE FORMATTER %s", wrap)
        return wrap


@dataclass(repr=False, order=False)
class GenFormatter(VolatileFormatter[Callable[[Generator], Tv], Tv]):
    as_value: Optional[Union[Type, Callable]] = tuple

    @classmethod
    def source_class(cls) -> Type[Generator]:
        return Generator

    def wrap_volatile(self) -> Tv:
        assert self._volatile is None, "wrap_volatile called over a cached value"
        wrap = self.as_value
        v = wrap(self.source)
        self.log_trace("VOLATILE WRAPPED %s", repr(v))
        formatter = self.mapping.ensure_formatter(v, self.key_for(v))
        self.log_trace("VOLATILE FORMATTER %s", formatter)
        return formatter


##
## MkVars
##


@dataclass(repr=False, order=False)
class MkVars(UserDict[str, MkVarsSource]):
    """Mapping type for macro-like expansion of formatted string values"""

    mapping: Mapping[str, MkVarsSource] = field(default_factory=dict)
    # fmt: off
    use_logging: Union[bool, logging.Logger] = "MKVARS_LOG_VERBOSE" in os.environ
    # fmt: on

    formatters: Sequence[Type[MkFormatter]] = field(default_factory=list)
    formatter_dispatch: Sequence[Type] = field(default_factory=list)
    evaluate: bool = True

    def formatter_table(self) -> Mapping[Type, Type[MkFormatter]]:
        """return a mapping of the formatter dispatch table for this MkVars instance

        ## See Also

        - `mkvars()`
        - `init_formatters()`
        - `ensure_formatter_class()`
        - `formatter_class()`
        """
        return MappingProxyType(dict(zip(self.formatter_dispatch, self.formatters)))

    def __str__(self):
        keys = (repr(k) for k in self.keys())
        return "<%s (%s)>" % (self.__class__.__name__, ", ".join(keys))

    def __repr__(self):
        keys = (repr(k) for k in self.keys())
        return "<%s at 0x%x (%s)>" % (
            self.__class__.__qualname__,
            id(self),
            ", ".join(keys),
        )

    @property
    def data(self):
        ## integration with the UserDict API
        return self.mapping

    @classmethod
    @property
    def logger(cls):
        if hasattr(cls, "_logger"):
            return cls._logger
        else:
            return cls.logger_init()

    @classmethod
    def logger_init(cls):
        if False:
            pass
        else:
            level = (LogLevel.TRACE if "MKVARS_LOG_VERBOSE" in os.environ else LogLevel.WARNING)
            logger = get_logger(cls.__class__.__module__, level=level, handler_class = "logging.StreamHandler")
            cls._logger = logger
            return logger

    def __getattr__(self, name: str):
        """Implementation for attribute-based reference to the mapping table of this MkVars"""
        if not (name.startswith("_") or name.startswith("log")):
            self.log_debug("GETATTR %s", name)
        try:
            mapped = self.__getitem__(name)
        except KeyError:
            raise AttributeError("Attribute not found", name, self)
        return mapped

    def __getitem__(self, name: str):
        log_get = not ((name.startswith("_") or name.startswith("log")))
        if log_get:
            self.log_debug("GETITEM %s", name)
        item = super().__getitem__(name)
        if isinstance(item, MkFormatter):
            value = item.parse()
            if log_get:
                self.log_debug("GETITEM %s => %s", name, value)
            return value
        else:
            if log_get:
                self.log_debug("GETITEM %s LITERAL => %s", name, value)
            return item

    def __setitem__(self, key: str, value):
        if not key.startswith("_"):
            self.log_debug("SETITEM %s  => %s", key, value)
        if isinstance(value, MkFormatter):
            super().__setitem__(key, value)
        else:
            self.ensure_formatter(value, key)

    def copy(self):
        self.log_debug("COPY")
        newmap = self.mapping.copy()
        ## approximating a tuple.copy()
        formatters = tuple(fcls for fcls in self.formatters)
        disp = tuple(cls for cls in self.formatter_dispatch)
        ## copy formatters
        mapping = self.mapping
        nrmapped = len(mapping)
        data = [False] * nrmapped
        items = tuple(mapping.items())
        for n in range(0, nrmapped):
            nth = items[n]
            key = nth[0]
            value = nth[1]
            if hasattr(value, "copy"):
                copy = value.copy()
            else:
                copy = value
            data[n] = (
                key,
                copy,
            )
        newmap = mapping.__class__(data)
        dup = dc.replace(
            self, mapping=newmap, formatters=formatters, formatter_dispatch=disp
        )
        ## reset all formatters in the copy
        dup.reset()
        self.log_trace("COPY => %r", dup)
        return dup

    def reset(self):
        self.evaluate = True
        self.log_debug("RESET")
        for value in self.values():
            if isinstance(value, MkFormatter):
                value.reset()

    def log_debug(self, message, *args):
        logger = self.logger
        if logger:
            logger.log(
                LogLevel.TRACE,
                "! %x %s " + message,
                id(self),
                self.__class__.__name__,
                *args,
            )

    def log_trace(self, message, *args):
        self.log_debug(
            "! %x %s .. " + message, id(self), self.__class__.__name__, *args
        )

    def parse(
        # fmt: off
        self, obj: MkVarsSource, kwargs: Optional[MkVarsMap] = None,
        return_items=False
        # fmt: on
    ):
        """Process a `MkVarsSource` value for expansions from callbacks and `str.format()`.

        **Ed. Note:** This docstring applies to an earlier revision of
        `parse()` using a generator semantics, with `parse()` implemented
        directly in `MkVars`. `parse()` has been updated to directly
        return each parsed value, after dispatch onto the `MkFormatter`
        table of the `MkVars` instance.

        ## Earlier Documentation

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
        if kwargs is None:
            kwargs = self

        self.log_trace("PARSE %s", repr(obj))

        formatter = self.ensure_formatter(obj)
        self.log_trace("PARSE %s @ formatter %s", repr(obj), formatter)
        rslt = formatter.parse()
        self.log_trace("PARSE %s => %s", repr(obj), repr(rslt))
        return rslt

    def eval(self) -> bool:
        ## returns a value indicating whether the instance was newly
        ## evaluated under the call
        if self.evaluate:
            for key, source in self.mapping.items():
                self.log_trace("SETVARS %s %s", key, source)
                value = self.parse(source, None)
                self.log_trace("SETVARS %s => %s", key, repr(value))
                self[key] = value
            self.evaluate = False
            return True
        else:
            return False

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

        self.log_debug("SETVARS %s", self)
        for key, source in kwargs.items():
            self.log_trace("SETVARS %s %s", key, source)
            value = self.parse(source, None)
            self.log_trace("SETVARS %s => %s", key, repr(value))
            self[key] = value

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
        self.log_debug("DUP %s => %s", self, mock)
        mock.update(kwargs)
        return mock

    def define(self, **values):
        self.log_debug("DEFINE %s", repr(values))
        return self.update(values)

    def update(self, *args, **values):
        self.log_debug("UPDATE %s %s", repr(args), repr(values))
        self.reset()
        return super().update(*args, **values)

    def value(self, source: MkVarsSource):
        self.log_debug("VALUE %s", repr(source))
        return self.parse(source, self)

    def cmd(self, source: Union[str, Callable[[], str]]):
        self.log_debug("CMD %s", repr(source))
        return shlex.split(self.value(source))

    def ensure_formatter_class(self, formatter: Type):
        formatters = self.formatters
        if formatter not in formatters:
            fcls = formatter.source_class()
            mro = fcls.__mro__
            dispatch = self.formatter_dispatch
            dispatch_table = dict(zip(dispatch, formatters))

            def the_formatter(cls):
                if cls in mro and cls not in dispatch:
                    return formatter
                else:
                    return dispatch_table[cls]

            # fmt: off
            new_dispatch = tuple(merge_mro((fcls,*dispatch,)))
            new_table = list(
                zip(new_dispatch, (the_formatter(cls) for cls in new_dispatch))
            )
            # fmt: on

            self.formatter_dispatch = tuple(d[0] for d in new_table)
            self.formatters = tuple(d[1] for d in new_table)

    def init_formatters(self):
        for cls in (
            MkFormatter,
            GenFormatter,
            SeqFormatter,
            MapFormatter,
            PathFormatter,
            CallableFormatter,
            StrFormatter,
        ):
            self.ensure_formatter_class(cls)

    def formatter_class(self, obj):
        ## return the MkFormatter class to use when creating a formatter for the object
        ## as under __getitem__
        dispatch = self.formatter_dispatch
        count = len(dispatch)
        found = None
        for n in range(0, count):
            dcls = dispatch[n]
            if isinstance(obj, dcls):
                found = self.formatters[n]
                break
        if found is None:
            cls = obj.__class__
            raise ValueError("No formatter class found", cls)
        else:
            return found

    def ensure_formatter(self, source: Any, key: Optional[str] = None, **initargs):
        if isinstance(source, MkFormatter):
            return source
        else:
            cls = self.formatter_class(source)
            initargs["key"] = key
            initargs["source"] = source
            if "mapping" not in initargs:
                initargs["mapping"] = self
            self.log_debug("ENSURE_FORMATTER %s %s", cls.__name__, key)
            formatter = cls(**initargs)
            self.log_debug("ENSURE_FORMATTER => %s", formatter)
            if isinstance(key, str):
                self.__setitem__(key, formatter)
            return formatter

    @classmethod
    def mkvars(cls, *args, **values):
        """create a new MkVars instance, intialized with common formatters

        ## Usage

        [FIXME docs needed]

        ## See Also

        - `init_formatters()`
        - `update()`
        """
        mkv = cls(*args)
        mkv.init_formatters()
        mkv.update(values)
        return mkv


##
## mkvars utility functions
##


def optional_files(*files: Sequence[str]) -> Generator[str, None, None]:
    for pathname in files:
        if os.path.exists(pathname):
            yield pathname


def venv_bindir(venv_dir: str) -> str:
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
