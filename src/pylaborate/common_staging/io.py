# pyalborate.common.io (staging)

from .naming import export
from .classlib import ContextManager

from dataclasses import dataclass
from pathlib import Path
from typing import IO, Optional, TypeAlias


# type of file values for PolyIO
PolyIOFile: TypeAlias = str | Path | IO


@dataclass(slots=True, frozen=False, eq=False, order=False)
class PolyIO(ContextManager):
    '''
    Polymorphic I/O class (context manager)
    '''
    file: PolyIOFile
    close_after: bool
    flush_after: bool
    open_args: dict
    io: Optional[IO]

    def __init__(self, file: PolyIOFile, close_after: Optional[bool] = None, flush_after: bool = True, **open_args):
        close = None
        if close_after is None:
            close = not isinstance(file, IO)
        else:
            close = close_after
        self.close_after = close
        self.flush_after = flush_after
        self.file = file
        self.open_args = open_args
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

    def open(self, file: Optional[PolyIOFile] = None, close_after=None, **open_args):
        io = self.io
        if file:
            if io is not None:
                raise RuntimeError(
                    "Stream already initialized", self, io, file)
        else:
            # no file provided to open()
            file = self.file
        if isinstance(file, IO):
            io = file
        else:
            io = open(file, **open_args)
        self.file = file
        self.io = io
        self.open_args = open_args
        return io

    def __call__(self, file: Optional[PolyIOFile] = None, close_after=None, **open_args):
        return self.open(file, close_after=close_after, **open_args)

    def __enter__(self) -> None:
        return self.open()

    def __exit__(self, exc_type, exc_value, traceback):
        if self.close_after:
            self.io.close()
        self.io = None


# autopep8: off
# fmt: off
__all__ = []
export(__name__, __all__, 'PolyIOFile', PolyIO)
