'''Type definitions for I/O'''

import os
from pathlib import Path
from typing import Annotated, Union
from typing_extensions import TypeAlias

PathArg: Annotated[
    TypeAlias, "Generalized filesystem pathname type"
] = Union[str, Path, os.PathLike]

__all__ = ("PathArg",)
