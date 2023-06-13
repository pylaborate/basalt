## demap - pylaborate.common_staging
"""A (non-optimal) mapping implementation for Deque"""

from collections import deque
from collections.abc import Sequence, Mapping, MutableMapping
from dataclasses import dataclass
from contextlib import contextmanager
from typing import Callable, Generator, Generic, Iterable, Optional, Tuple, Union
from typing_extensions import TypeAlias, TypeVar

T = TypeVar("T")

@dataclass(frozen = True, slots = True, eq = False, order = False)
class GenBounded:
    ## TBD - protoype for Demap methods: keys, items, values
    generator: Generator
    source: Iterable

    def __len__(self):
        return len(self.source)

    def __next__(self):
        return next(self.generator)

    def __iter__(self):
        return self.generator


Tv = TypeVar("Tv")

@dataclass(frozen = True, slots = True, eq = False, order = False)
class QueConsumer(Generic[T, Tv]):
    ## TBD
    que: deque

    def call(self, value: T) -> Tv:
        return value

    def __next__(self):
        try:
            value = self.que.popleft()
        except IndexError:
            raise StopIteration
        return self.call(value)

    def __len__(self):
        return len(self.que)

    def __iter__(self):
        return self

class KeyConsumer(QueConsumer["DemapEntry", str]):
    def call(self, item) -> str:
        return item.key

class ValueConsumer(QueConsumer["DemapEntry", T]):
    def call(self, item) -> T:
        return item.value

class ItemConsumer(QueConsumer["DemapEntry", Tuple[str, T]]):
    def call(self, item) -> Tuple[str, T]:
        return (item.key, item.value,)



class DemapEntry(Generic[T]):
    """key and value storage for `Demap`"""

    @property
    def key(self) -> str:
        return self._key

    @key.setter
    def key(self, new_value: str):
        # fmt: off
        raise TypeError("Operation not supported: set key value in an initialized %s",
                        self.__class__.__name__)
        # fmt: on

    @property
    def keyhash(self) -> int:
        return self._keyhash

    @keyhash.setter
    def keyhash(self, new_value: int):
        # fmt: off
        raise TypeError("Operation not supported: set keyhash value in an initialized %s",
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

    def __iter__(self):
        yield self.key
        yield self.value

    def __repr__(self):
        # fmt: off
        return "<%s at 0x%x %s = %s>" % (self.__class__.__name__, id(self),
                                         self.key, repr(self.value))
        # fmt: on

    def __str__(self):
        return "%s(%r, %s)" % (self.__class__.__name__, self.key, repr(self.value))

# fmt: off
DemapInitial: TypeAlias = Optional[Union[Mapping[str, T], Sequence[Sequence[str, T]]]], deque
# fmt: on

#class Demap(MutableMapping[str, T]):
class Demap(Generic[T]):
    """Mapping type based on a deque"""

    def __init__(self, initial: DemapInitial = None):
        ## FIXME add an initarg fold_keys = True to avoid the key display under __repr__, __str__
        initial_items = [False] * len(initial) if initial else ()
        n = 0
        if isinstance(initial, deque):
            self._storage = initial
            return
        elif isinstance(initial, Mapping):
            for key in initial:
                initial_items[n] = DemapEntry(key, initial[key])
                n = n + 1
        elif isinstance(initial, Sequence):
            for key, value in initial:
                initial_items[n] = DemapEntry(key, value)
                n = n + 1
        ##  not notably more optimal if the deque is bounded to a fixed size
        self._storage = deque(initial_items)

    @contextmanager
    def yield_for(self, key: str):
        ## Implementation Notes:
        ##
        ## utility context for some methods in the mapping protocol
        ##
        ## This context manager should yield exactly one value
        ## - yields the DemapEntry for any found key
        ## - yields None if the key was not found
        ##
        ## Tested indirectly, in :test/**/test_mkvars.py
        ##
        ## Not thread-safe
        h = hash(key)
        q = self._storage
        count = len(q)
        for n in range(0, count):
            item = q[n]
            ## the pre-hashing approach may be relatively more optimal,
            ## contrasted to a string-equal comparison of keys
            if item.keyhash == h:
                yield item
                return
        yield None

    @contextmanager
    def yield_indexed_for(self, key: str):
        ## Implementation Notes:
        ##
        ## utility context for __delitem__
        ##
        ## similar to yield_for(), but with a different yield syntax:
        ## - yields (item, index,) if found
        ## - yields (none, -1,) if not found
        h = hash(key)
        q = self._storage
        count = len(q)
        for n in range(0, count):
            item = q[n]
            if item.keyhash == h:
                yield item, n
                return
            n = n + 1
        yield (None, -1)

    # @contextmanager
    # def yield_indexed(self):
    #     ## TBD @ usage, public API
    #     q = self._storage
    #     n = 0
    #     for item in q:
    #         yield item, n
    #         n = n + 1

    # def each(self):
    #     ## TBD @ usage, public API
    #     return (yield from self._storage)

    def __copy__(self):
        return self.__class__(self._queue.copy())

    def __missing__(self, key: str):
        ## FIXME return a default, if default_set
        raise KeyError(key)

    def __contains__(self, key: str):
        with self.yield_for(key) as first:
            if first is None:
                return False
            else:
                return True

    def __getitem__(self, key: str) -> T:
        with self.yield_for(key) as first:
            if first is None:
                return self.__missing__(key)
            else:
                return first.value

    def __setitem__(self, key: str, value: T):
        ## Implementation Notes:
        ##
        ## Returns a boolean value, indicating whether
        ## the demap que was modified in the call,
        ## i.e whether a new entry was created
        ## for the key
        ##
        with self.yield_for(key) as first:
            if first is None:
                ## appendleft may be slightly more optimal here ?
                self._storage.appendleft(DemapEntry(key, value))
                ## or perhaps not ...
                # self._storage.append(DemapEntry(key, value))
                return True
            else:
                first.value = value
                return False

    def __delitem__(self, key: str):
        ## not thread-safe
        q = self._storage
        with self.yield_indexed_for(key) as (first, index,):
            if first is None:
                return self.__missing__(key)
            else:
                del q[index]
                return first.value

    def __iter__(self):
        return self.keys()

    def __reversed__(self):
        revq = self._storage.copy()
        revq.reverse()
        return KeyConsumer(revq)

    def __len__(self):
        return len(self._storage)

    def keys(self):
        ## first prototype:
        # storage = self._storage
        # return GenBounded((item.key for item in storage), storage)
        ## still no substantial improvement here:
        proxy = self._storage.copy()
        return KeyConsumer(proxy)

    def values(self):
        # storage = self._storage
        # return GenBounded((item.value for item in storage), storage)
        ## ...
        proxy = self._storage.copy()
        return ValueConsumer(proxy)

    def items(self):
        # storage = self._storage
        # return GenBounded(((item.key, item.value,) for item in storage), storage)
        ## ...
        proxy = self._storage.copy()
        return ItemConsumer(proxy)

    def get(self, key: str, default = None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def copy(self):
        return self.__copy__()

    def update(self, mapping):
        if isinstance(mapping, Mapping):
            for key in mapping:
                self[key] = mapping[key]
        elif isinstance(mapping, Sequence):
            for key, value in mapping:
                self[key] = value

    def remove(self, key: str):
        del self[key]

    def __str__(self):
        keys = (item.key for item in self._storage)
        ## FIXME this may be excessive, even limited to the keys of the mapping:
        return "%s(%s)" % (self.__class__.__qualname__, ", ".join(keys))

    def __repr__(self):
        keys = (item.key for item in self._storage)
        # fmt: off
        return "<%s at 0x%x (%s)>" % (self.__class__.__qualname__, id(self),
                                      ", ".join(keys))
        # fmt: on


## FIXME: Extend Demap for concurrent applications:
## - acquire a lock before each dispatch to super()
## - SyncDemap, using a threading lock
## - AsyncDemap, using an aio lock
## - implement tests
