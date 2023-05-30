## io.py
'''Utilities for stream I/O'''

from pathlib import Path
from typing import Union
from typing_extensions import Annotated, TypeAlias


PathArg: Annotated[TypeAlias, "Generalized filesystem pathname indicator"] = Union[str, Path]


__all__ = ['PathArg']
