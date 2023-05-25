# pyalborate.common.io (staging)

from .naming import export

from dataclasses import dataclass
import os
from pathlib import Path
from typing_extensions import TypeAlias
from typing import IO, Optional, Union


# type of file values for PolyIO
PolyIOFile: TypeAlias = Union[str, Path, IO]


@dataclass(slots=True, frozen=False, eq=False, order=False)  # type: ignore
class PolyIO():
    '''
    Polymorphic I/O class (context manager)
    '''
    file: PolyIOFile
    close_after: bool
    flush_after: bool
    open_args: dict
    io: Optional[IO]

    def __init__(self, file: PolyIOFile, close_after: bool = True, flush_after: bool = True, **open_args):
        self.file = os.path.expanduser(file)
        self.close_after = close_after
        self.flush_after = flush_after
        self.open_args = open_args
        ## not thread-safe
        self.io = None

    def close(self, flush: Optional[bool] = False):
        io = self.io
        if io and self.flush_after:
            ## FIXME also implement __write__ with flush-after-write support
            io.flush()
        if io is not None:
            return io.close()
        else:
            return False

    def open(self) -> IO:
        file = self.file
        open_args = self.open_args
        io = open(file, **open_args)
        self.io = io
        return io

    def __call__(self):
        return self.open()

    def __enter__(self) -> IO:
        return self.open()

    def __exit__(self, exc_type, exc_value, traceback):
        if self.close_after:
            self.io.close()
        self.io = None


# autopep8: off
# fmt: off
__all__ = []  # type: ignore
export(__name__, __all__, 'PolyIOFile', PolyIO)
