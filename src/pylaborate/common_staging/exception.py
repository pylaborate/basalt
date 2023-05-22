# pyalborate.common.exception (staging)

from .funlib import export

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, IO


class GeneralException(Exception):
    def __init__(self, *args, **kwargs):
        items = kwargs.items()
        super().__init__(*args)
        self._keywords = kwargs
        for it in items:
            setattr(self, str(it[0]), it[1])

    def _opts_str(self):
        tail_args = [str(val) for val in self.args]
        tail_args.extend(
            [str(k) + "=" + str(self._keywords[k]) for k in self._keywords]
        )
        return ", ".join(tail_args)

    def __repr__(self):
        clsname = self.__class__.__name__
        return clsname + "(" + self._opts_str() + ")"

    def __str__(self):
        return "(" + self._opts_str() + ")"


@dataclass
class FileError(GeneralException, RuntimeError):
    # FIXME py util / exceptions
    file: Optional[str | Path | IO]


# autopep8: off
# fmt: off
__all__ = []
export(__name__, __all__, GeneralException, FileError)
