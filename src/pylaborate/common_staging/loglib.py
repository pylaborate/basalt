## loglib - pylaborate.common_staging

from enum import Enum, IntEnum
from .naming import bind_enum, export, export_annotated, get_object
from .iterlib import merge_map
import logging
## type hints
from types import ModuleType
from typing import Optional, Union, Type


class LogLevel(IntEnum):
    """log level enum, extended with the trace log level

    ## Usage

    The `LogLevel` enum provides a form of constant reference context
    for the _log level_ argument in calls to `logger.Logging.log()`

    This enum defines a non-normative `TRACE` log level, at one half of
    the priority of the `DEBUG` log level.

    ## See Also

    `ensure_log_levels()`
    """
    CRITICAL = logging.CRITICAL
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    INFO = logging.INFO
    DEBUG = logging.DEBUG
    ## new: TRACE log level
    TRACE = int(logging.DEBUG / 2)
    NOTSET = logging.NOTSET

bind_enum(LogLevel, __name__)

def ensure_log_levels(level_enum: Enum = LogLevel):
    """Ensure that each log _level defined_ in `LogLevel` will denote a
    logging level registered under the `logging` module"""
    levels = logging.getLevelNamesMapping().values()
    for m in level_enum.__members__.values():
        value = m.value
        if value not in levels:
            logging.addLevelName(value, m.name)

def create_logging_config(
    # fmt: off
    name: Optional[str] = "log",
    disable_existing_loggers: bool = False,
    incremental: bool = False,
    handler: Optional[str] = "consoleHandler",
    handler_class: Union[Type, str] = logging.StreamHandler,
    level: LogLevel = LogLevel.INFO,
    **kwargs
    # fmt: on
):
    """Return a mapping for a logging configuration, modified by the provided args

    ## Usage

    `name`
    : the name of the logger to create. When called from `get_logger()`, this name
      will be determined per the value of the `context` arg to `get_logger()`.

    `handler`
    : if not a _falsey_ value, the name of a logging handler to to create for
      the logger. This handler will be created using the provided `handler_class`
      and configured for the specified logging `level`. If a logging handler is
      not created here, generally a handler should be created by the caller
      and manually added to the logger, once configured for logging level,
      log format, etc.

    `kwargs`
    : arguments in a format compatible with `logging.config.dictConfig()`.
    """
    config = {
        "version": 1,
        "disable_existing_loggers": disable_existing_loggers,
        "incremental": incremental,
        "loggers": {name: {"level": level}},
    }
    if handler:
        config['loggers'][name]['handlers'] = [handler]
        if isinstance(handler_class, str):
            try:
                ## validate the handler class name, failing by side-effect
                ## if no class can be located for that name
                get_object(handler_class)
            except ValueError as exc:
                raise ValueError("Handler class not found",  handler_class) from exc
            clsname = handler_class
        else:
            clsname = handler_class.__module__ + "." + handler_class.__name__
        handler_config = {
            'class': clsname,
            'level': level
        }
        config['handlers'] = dict()
        config['handlers'][handler] = handler_config
    merge_map(config, kwargs)
    return config


def get_logger(context: Union[str, Type, ModuleType], **args):
    """return a logger for a provided `context`, configured per the provided `config`

    ## Usage

    `context`:
    : a string, or a class, module, or other named object. This value will be used to determine
      the name for the logger, both in the logger retrieval and  logger configuration procedures.

    `args`
    : arguments in a format compatible with `logging.config.dictConfig`. These arguments will
      be passed to `create_logging_config`

    returns the logger
    """
    config = dict(**args)
    if isinstance(context, str):
        name = context
    if "name" in args:
        name = args["name"]
    else:
        has_module = hasattr(context, "__module__")
        has_name = hasattr(context, "__name__")
        if has_module and has_name:
            name = "%s.%s" % (context.__module__, context.__name__)
        elif has_module:
            name = context.__module__
        elif has_name:
            name = context.__name__
        else:
            name = "log"
    config["name"] = name
    ensure_log_levels()
    logger = logging.getLogger(name)
    dct = create_logging_config(**config)
    logging.config.dictConfig(dct)
    return logger

__all__ = []
export(__name__, LogLevel, ensure_log_levels, create_logging_config, get_logger)

## export any TypeAlias values:
export_annotated(__name__)
