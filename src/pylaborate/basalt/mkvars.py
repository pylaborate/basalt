## mkvars - pylaborate.basalt
"""String macro expansion for Python, in a Make-like syntax"""

from collections import UserDict
from collections.abc import Callable, Generator, Mapping, Sequence

from dataclasses import dataclass, field

from itertools import chain
import os
from pathlib import Path
import shlex
import sys

from typing import Any, Iterable, Optional, Union

from typing_extensions import Self, TypeAlias, TypeVar

##
## Types
##

# fmt: off
MkVarsMap: TypeAlias = Union[Mapping[str, "MkVarsSource"], "MkVars"]

MkVarsSource: TypeAlias = Union[
    str, MkVarsMap, Iterable["MkVarsSource"], Sequence["MkVarsSource"],
    Callable[[], "MkVarsSource"]
]
# fmt: on

##
## MkVars
##

@dataclass
class MkVars(UserDict[str, MkVarsSource]):
    """Mapping type for macro-like expansion of formatted string values"""

    mapping: MkVarsSource = field(default_factory = dict)

    def __getattr__(self, name: str):
        """Implementation for attribute-based reference to the mapping table of this MkVars"""
        ## FIXME also implement __delattr__
        ## FIXME move to AttrMap (common_staging)
        try:
            # return self.__getitem__(name)
            return self.mapping.__getitem__(name)
        except KeyError:
            ## TBD dispatch under os.environ
            raise AttributeError("Attribute not found", name, self)

    # def __len__(self):
    #     return len(self.mapping)

    @property
    def data(self):
        ## for UserDict
        return self.mapping

    def copy(self):
        m = self.mapping.copy()
        new = self.__class__(m)
        return new

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
## mkvars utility functions
##


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
