## pylaborarte.basalt.__main__

import argparse
import asyncio as aio
from abc import abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, IntEnum
from io import StringIO
import inspect
import logging
import os
from pathlib import Path
import paver.misctasks as misctasks
import paver.tasks as tasks
import concurrent.futures as cofutures
import psutil
from pylaborate.common_staging import bind_enum, get_module, ModuleArg, origin_name, PathArg
import shellous
from shellous.redirect import Redirect
import shlex
import signal as nsig
import sys
import threading
import traceback
from types import FrameType, MappingProxyType, ModuleType, TracebackType
from typing import Any, Callable, Generic, Generator, List, Literal, Mapping, Optional, Protocol, Sequence, Tuple, Union
from typing_extensions import Self, Type, TypeVar, TypeVarTuple


T = TypeVar("T")

class FutureType(Protocol[T]):
    ## protocol class for  minimum API, compatible with
    ## concurrentfutures.Future and asyuncio.Future
    ##
    ## Implementation Notes: Comptability:
    ##
    ## - a timeout arg is not accepted in:
    ##   - asyncio.Future.result()
    ##   - asyncio.Future.exception()
    ##
    ## - a context arg is not accepted in:
    ##   - concurrent.futures.Future.add_done_callback()
    ##
    ## - not implemented in concurrent.futures.Future:
    ##   - remove_done_callback()
    ##   - get_loop()

    @abstractmethod
    def cancel(self):
        return NotImplemented

    @abstractmethod
    def cancelled(self) -> bool:
        return NotImplemented

    @abstractmethod
    def running(self) -> bool:
        return NotImplemented

    @abstractmethod
    def done(self) -> bool:
        return NotImplemented

    @abstractmethod
    def result(self) -> T:
        return NotImplemented

    @abstractmethod
    def exception(self) -> Optional[Exception]:
        return NotImplemented

    @abstractmethod
    def add_done_callback(self, callback: Callable[[Self], Any]):
        return NotImplemented

    @abstractmethod
    def set_result(self, result: T):
        return NotImplemented

    @abstractmethod
    def set_exception(self, exception: Exception):
        return NotImplemented


class SemaphoreType(Protocol):
    ## protocol class for  minimum API, compatible with
    ## concurrentfutures.Future and asyuncio.Future
    ##
    ## Implementation Notes: Comptability:
    ##
    ## - asyncio.Semaphore does not support a 'timeout' or 'blocking'
    ##   arg on acquire()
    ##
    ## - asyncio.Semaphore does not support an increment arg
    ##
    @abstractmethod
    def acquire():
        return NotImplemented

    @abstractmethod
    def release():
        return NotImplemented


SignalHandlerLiteral: TypeVar = Union[Literal[nsig.SIG_DFL], Literal[nsig.SIG_IGN]]
SignalHandlerCallable: TypeVar = Callable[[int, FrameType], Any]
SignalHandlerType: TypeVar = Union[SignalHandlerCallable, SignalHandlerLiteral]

@dataclass(init = True, eq = False, order = False, frozen=True)
class SigContext():
    sigt: nsig.Signals
    previous: SignalHandlerType
    handler: SignalHandlerType

    @classmethod
    def activate(cls, sigt: nsig.Signals, handler: SignalHandlerType) -> Self:
        previous = nsig.signal(sigt, handler)
        return cls(sigt, previous, handler)

    @staticmethod
    def get_signal(signum: Union[nsig.Signals, int]):
        if isinstance(signum, nsig.Signal):
            return signum
        else:
            return nsig.Signal(signum)

    def restore(self):
        nsig.signal(self.sigt, self.previous)


@dataclass(init = True, eq = False, order = False, frozen=True)
class RunContext():
    ## utility class for sharing state information from Basalt.amain
    ## to other utility classes implemented below
    loop: aio.AbstractEventLoop
    exit_future: FutureType
    workers_semaphore: SemaphoreType
    executor: cofutures.Executor


@dataclass(eq = False, order = False, frozen=False)
class FutureManager():
    ## utility class for TaskProxyBase implementations
    ##
    ## provdies a rudimentary context manager protocol for a call using a future
    ## for return value / exception storage
    ##

    task: Any
    future: FutureType
    # ^ the future to manage, mainly under __exit__
    exception_callback: Optional[Callable[[Exception, Optional[List]], Any]] = None
    # ^ optional callback on event of exception
    set_exception: bool = True
    # ^ whether to set any exception to the future
    # ^ False for the main exit_future under -k/--continue

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exception, tbk):
        exc_cb = self.exception_callback
        try:
            # fmt: off
            Basalt.instance.logger.log(LogLevel.TRACE,
                                       "%s: __exit__ in FutureManager for %s",
                                       self.task, self.future)
            # fmt: on
        except Exception:
            if exc_cb:
                exc_cb(self.task, *sys.exc_info)
        if exception:
            if self.set_exception:
                fut = self.future
                if not fut.done():
                    try:
                        fut.set_exception(exception)
                    except Exception:
                        ## if there's an error while setting the future's exception,
                        ## ensure it's logged or printed, with traceback
                        etyp, eargs, tbk = sys.exc_info
                        if exc_cb:
                            exc_cb(self.task, etyp, eargs, tbk)
                        else:
                            traceback.print_exc(eargs)
                            traceback.print_tb(tbk)
            if exc_cb:
                exc_cb(self.task, exc_type, exception.args, tbk)


Ts = TypeVarTuple('Ts')
Tsk = TypeVar('Tsk')

@dataclass(eq = False, order = False, frozen=True, init=True, repr=False)
class TaskProxyBase(Generic[Tsk, T]):
    task: Tsk
    # ^ Paver task providing the func that this task proxy will dispatch to

    receiver: T
    # ^ the Basalt runtime instance

    run_context: RunContext
    # ^  information specific to active the Basalt runtime

    run_future: FutureType
    # ^ must be externally provided. may be a cofutures.Future

    depends: Sequence[str]
    # ^ tuple of task names, for all tasks that the provided task depends on

    rdepends: Sequence[str]
    # ^ tasks names for tasks that depend on the provided task

    launch_map: "TaskLaunchMap"
    # ^ used for locating reverse-dependent tasks under cancel_rdeps()

    def __hash__(self):
        return hash((self.task.name, self.run_future,))

    def __str__(self):
        task = self.task
        name = task.name if task else repr(None)
        future = self.run_future
        # fmt: off
        return "<%s %s [%s] at 0x%x>" % (
            self.__class__.__qualname__,  name, future, id(self)
        )
        # fmt: on

    def __repr__(self):
        return str(self)

    @property
    def workers_semaphore(self):
        return self.run_context.workers_semaphore

    @property
    def exit_future(self):
        return self.run_context.exit_future

    @property
    def stop_on_exception(self):
        return self.receiver.stop_on_exception

    @property
    def loop(self):
        return self.run_context.loop

    def can_run(self) -> bool:
        runnable = not self.run_context.exit_future.cancelled()
        if not runnable:
            return False
        for task in self.depends:
            entry = self.launch_map.get_entry(task)
            if entry.run_future.done():
                runnable = False
                break
        return runnable

    def cancel_rdeps(self, *_):
        ## cancel all tasks that depend on this task, mainly on event of
        ## build failure
        ##
        ## when called under managed_context() the call would provide
        ## exception information via args to the call
        ##
        ## The exception information would be captured under the
        ## FutureManager context for the main exit_future, and
        ## will not be used here
        ##
        for task in self.rdepends:
            entry = self.launch_map.get_entry(task)
            entry.run_future.cancel()

    def cancel(self, cancel_rdeps: bool = True):
        ## called from TaskLaunchMap for all scheduled tasks, with cancel_rdeps = False
        self.run_future.cancel()
        if cancel_rdeps:
            self.cancel_rdeps()

    def defer_exception(self, *args, **kwargs):
        ## utility method for the managed_context, dispatching from this task proxy
        ## to pass any exception information to the Basalt instance
        self.receiver.push_exception_info(*args, **kwargs)

    @contextmanager
    def managed_context(self):
        ## context manager for task-launch methods in TaskProxy implementation classes
        ##
        ## usage:
        ##
        ## - ensuring that the task launch call will not be entered, if either of the
        ##   main exit_future or task-local run_future has been cancelled
        ##
        ## - capturing any exception information within the context of the yield,
        ##   via FutureManager
        ##
        ## - producing log information via FutureManager, when -vvv/trace
        ##
        ## - used twice for each SyncTaskProxy, once in the task-launch method,
        ##   once in the call dispatched to the executor
        ##
        ## - the workers semaphore should be held within this context, once
        ##   for each task launch m ethod
        ##
        exit_future = self.exit_future
        run_future = self.run_future

        with FutureManager(self.task, exit_future, self.defer_exception, self.stop_on_exception):
            with FutureManager(self.task, run_future, self.cancel_rdeps, True):
                if not exit_future.cancelled():
                    if not run_future.cancelled():
                        yield
    def get_kwargs(self):
        ## return the set of kwargs to provide to the task func.
        ##
        ## Similar to task dispatching in Paver, this will use
        ## attributes of the Paver environment object.
        ##
        ## For args in {env, sh, future} not defined with a default
        ## in the task function, those args will be provided with a
        ## default value hard-coded below
        ##
        ## This implementation is referenced onto
        ## paver.tasks.environemnt._run_task()
        ##
        task = self.task
        taskname = task.shortname
        taskfunc = task.func
        spec = inspect.getfullargspec(taskfunc)
        funcargs = spec.args
        nr_funcargs = len(funcargs)
        defaults = spec.defaults
        nr_defaults = len(defaults) if defaults else 0
        first_default = (nr_funcargs - nr_defaults) if defaults else None
        kwodefaults = spec.kwonlydefaults

        env = self.receiver.environment
        env_opts = env.options
        task_opts = getattr(env_opts, taskname) if hasattr(env_opts, taskname) else None
        env_vars = dir(env)
        use_args = dict()  # the keyword args to pass
        n = 0
        for n in range(0, nr_funcargs):
            arg = funcargs[n]
            ##
            ## the order of precedence here may differ slightly, with
            ## regards to paver _run_task
            ##
            if task_opts and hasattr(task_opts, arg):
                ## if the task has a named paver Bunch or other dict-like structure
                ## under environment.options, i.e environment.options.<task_name>
                ## and if the arg is provided with a value in that structure,
                ## then setting the function arg from the value provided there
                ##
                ##
                ## this is normally completed during paver.tasks._parse_command_line()
                ## => <task>.parse_args() || <task>._consume_nargs(...)
                ## at least for tasks specified at the cmdline (?).
                ##
                ## If a task is not specified at the cmdline, it may not by default
                ## have a Bunch under environment.options - whether or not the task
                ## was defined with @cmdopts/@consume_args/@consume_nargs (?)
                ##
                use_args[arg] = getattr(task_opts, arg)
            elif arg in env_vars:
                use_args[arg] = getattr(env, arg)
            elif first_default and n >= first_default:
                default = defaults[n - first_default]
                use_args[arg] = default
            elif kwodefaults and arg in kwodefaults:
                use_args[arg] = kwodefaults[arg]
            elif arg == 'env':
                use_args[arg] = env
            elif arg == 'sh':
                ## for integration with shellous
                use_args[arg] = self.receiver.shell_context
            elif arg == 'future':
                ## for cancellable 'sh' handling
                use_args[arg] = self.run_future
            else:
                # fmt: off
                raise tasks.PavementError(
                    "Arg %r for task function %r has no default, and no value is defined "
                    "in the Paver environment" % (arg, task.name,),
                    arg, task, env)
                # fmt: on
        return use_args

@dataclass(eq = False, order = False, frozen=True, init=False, repr=False)
class SyncTaskProxy(TaskProxyBase[tasks.Task, "Basalt"]):
    '''task proxy for dispatch to synchronous task functions'''

    @property
    def executor(self):
        return self.run_context.executor

    def callback(self):
        ## callback for tasks under the executor,
        ## may be launched in individual threads
        with self.managed_context():
            task = self.task
            taskfunc = task.func
            kwargs = self.get_kwargs()
            if kwargs and len(kwargs) is int(0):
                kwargs = None

            if hasattr(task,'paver_constraint'):
                ## pre-exec function
                ##
                ## used under paver.virtual
                ## applied under paver.tasks.Task.call_task()
                task.paver_constraint()

            rslt = False
            if kwargs:
                rslt = taskfunc(**kwargs)
            else:
                rslt = taskfunc()

            run_future = self.run_future
            try:
                if not run_future.done():
                    run_future.set_result(rslt)
            except cofutures.CancelledError:
                pass
            return rslt

    async def launch_task(self):
        if not self.can_run():
            self.cancel()
            return

        sem = self.workers_semaphore
        executor = self.executor
        run_future = self.run_future

        with self.managed_context():
            async with sem:
                taskname = self.task.name
                # fmt: off
                self.receiver.logger.log(LogLevel.INFO,
                                         "%s: Launching async task",
                                         taskname)
                # fmt: on

                hdl = executor.submit(self.callback)

                # fmt: off
                self.receiver.logger.log(LogLevel.TRACE,
                                         "%s: Call delivered to executor. co-handle: %r",
                                         taskname, hdl)
                # fmt: on

                if self.receiver.log_level <= LogLevel.TRACE:
                    def done_cb(cofuture):
                        nonlocal taskname, self
                        self.receiver.logger.log(
                            # fmt: off
                            LogLevel.TRACE, "%s: Executor thread finished. local future: %r",
                            taskname, cofuture
                            # fmt: on
                        )
                    hdl.add_done_callback(done_cb)

                duration = sys.getswitchinterval()
                try:
                    while not run_future.done():
                        await aio.sleep(duration)
                except (cofutures.CancelledError, aio.CancelledError,):
                    pass


                ## access the handle from the executor
                ##
                ## by side effect, this may ensure task completion within any thread
                ## created by the executor
                ##
                exc = None
                try:
                    exc = hdl.exception()
                except cofutures.CancelledError:
                    pass

                self.receiver.logger.log(LogLevel.DEBUG,
                                         "%s: Returning from task",
                                         taskname)

                if exc:
                    # fmt: off
                    self.receiver.logger.log(LogLevel.TRACE,
                                             "%s: Exception during launch_sync_task: %r",
                                             taskname, exc)
                    # fmt: on
                    ## record any exception that may have been missed under the callback
                    self.defer_exception(self.task, exc.__class__, exc.args)
                    if self.stop_on_exception:
                        if not self.exit_future.done():
                            self.exit_future.set_exception(exc)
                    if not self.run_future.done():
                        self.run_future.set_exception(exc)
                    return exc
                else:
                    # fmt: off
                    self.receiver.logger.log(LogLevel.TRACE,
                                             "%s: Returning from launch_sync_task, run_future %r",
                                             taskname, run_future)
                    # fmt: on
                    rslt = hdl.result()
                    run_future = self.run_future
                    if not run_future.done():
                        run_future.set_result(rslt)
                    return rslt


@dataclass(eq = False, order = False, frozen=True, repr=False)
class AsyncTaskProxy(TaskProxyBase[tasks.Task, "Basalt"]):
    '''task proxy for dispatch to asynchronous task functions'''

    async def launch_task(self):
        if not self.can_run():
            self.cancel()
            return

        run_future = self.run_future

        task = self.task
        taskfunc = task.func


        sem = self.workers_semaphore
        run_future = self.run_future
        with self.managed_context():
            # fmt: off
            self.receiver.logger.log(LogLevel.TRACE,
                                     "%s: context enter => %s",
                                     task, taskfunc)
            # fmt: on
            async with sem:

                # fmt: off
                self.receiver.logger.log(LogLevel.INFO,
                                         "%s: Launching synchronous task",
                                         task.name)
                # fmt: on

                kwargs = self.get_kwargs()
                if kwargs and len(kwargs) is int(0):
                    kwargs = None

                    if hasattr(task, 'paver_constraint'):
                        ## pre-exec function
                        ##
                        ## used under paver.virtual
                        ## applied under paver.tasks.Task.call_task()
                        task.paver_constraint()

                rslt = False
                try:
                    if kwargs:
                        rslt = await taskfunc(**kwargs)
                    else:
                        rslt = await taskfunc()
                    if not run_future.done():
                        run_future.set_result(rslt)
                except aio.CancelledError:
                    return False

                self.receiver.logger.log(LogLevel.DEBUG,
                                         "%s: Returning from task",
                                         task.name)
                return rslt

Tsk = TypeVar('Tsk', bound=tasks.Task)
Tx = TypeVar('Tx', bound=TaskProxyBase)


@dataclass(init = False, frozen = False, eq = False, order = False)
class TaskLaunchMap:

    run_context: RunContext
    build_order: Sequence[Tx]
    launch_map: Mapping[str, Tx]
    finalized: bool

    def __init__(self, run_context):
        self.run_context = run_context
        self.build_order = []
        self.launch_map =  dict()
        self.finalized = False

    def __hash__(self):
        return hash(self.build_order)

    def get_entry(self, task: Union[str,tasks.task]):
        name = None
        if isinstance(task, str):
            name = task
        else:
            name = task.name
        return self.launch_map[name]

    def cancel(self):
        for proxy in self.build_order:
            ## cancelling all tasks  by way of the build_order
            proxy.cancel(False)

    def proxy_class_for_task(self, task: Tsk) -> Type:
        func = task.func
        if inspect.iscoroutinefunction(func):
            return AsyncTaskProxy
        else:
            return SyncTaskProxy

    def init_run_future(self, task: Tsk) -> FutureType:
        func = task.func
        if inspect.iscoroutinefunction(func):
            ## aio futures @ async tasks ...
            loop = self.run_context.loop
            return aio.Future(loop = loop)
        else:
            ## cofutures @ sync tasks ...
            return cofutures.Future()

    def create_task_proxy(self, task: Tsk, receiver: T, run_context: RunContext, deps_data: Sequence[str] = (), rdeps_data: Sequence[str] = ()) -> Tx:
        if self.finalized:
            # fmt: off
            raise BoundValue("Unable to add task to a finalized map: %s" % repr(self))
            # fmt: on
        cls = self.proxy_class_for_task(task)
        run_future = self.init_run_future(task)
        inst = cls(task, receiver, run_context, run_future, tuple(deps_data), tuple(rdeps_data), self)
        self.build_order.append(inst)
        name = task.name
        self.launch_map[name] = inst
        return inst

    def finalize(self):
        if self.finalized:
            return False
        else:
            self.build_order = tuple(self.build_order)
            self.launch_map = MappingProxyType(self.launch_map)
            self.finalized = True
            return True

##
## Logging
##

class LogLevel(IntEnum):
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
    levels = logging.getLevelNamesMapping().values()
    for m in level_enum.__members__.values():
        value = m.value
        if value not in levels:
            logging.addLevelName(value, m.name)

##
## Argparse Support
##

@dataclass(init = False, eq = False, order = False, frozen=True)
class ArgparseAction():
    ## approximation of a StrEnum class,
    ## without portability issues
    STORE: str = "store"
    STORE_CONST: str = "store_const"
    STORE_TRUE: str = "store_true"
    STORE_FALSE: str = "store_false"
    APPEND: str = "append"
    APPEND_CONST: str = "append_const"
    COUNT: str = "count"
    HELP: str = "help"
    VERSION: str = "version"
    EXTEND: str = "extend"


@dataclass(init=False, eq=False, order=False)
class Cmdline:

    def __str__(self):
        return "<%s 0x%x>" % (self.__class__.__qualname__, id(self))

    def __repr__(self):
        return str(self)

    @classmethod
    def init_argparser(cls, instance: Self) -> argparse.ArgumentParser:
        """Initialize and return new options namespace object.

        This class method provides a _protocol form_ for initailizaing
        an argument parser for a `Cmdline` instance. This method would
        typically be used within the `consume_args()` instance method.

        This method may be overridden within any implementing class, such
        as to manage the arguments provided to the `argparse.ArgumentParser`
        constructor, and to set any defaults external to the constructor args.

        By default, the object returned from this method will be stored as
        the value of the `option_namespace` property for the provided
        `instance`, after the first call to `consume_args()` on that instance.

        The object returned from this class method will then be used to store
        any parsed options, pursuant of argument parsing within `consume_args()`
        """
        return argparse.ArgumentParser(prog=self.program_name)

    def __call__(self, *args):
        """[tentative] this method may be removed in a subsequent revision"""
        self.main(*args)

    def main(self, args=sys.argv[1:]) -> int:
        """protocol method - produces error text and returns a non-zero return code"""
        print("main() not implemented for %r" % self, file=sys.stderr)
        return 2

    @property
    def option_namespace(self) -> object:
        """return an options namespace object

        The object returned from this method will be applied together with
        the argument parser for the implementing `Cmdline` instance, in order
        to parse any command line arguments for the implementation.

        If this method would be overridden in an implementing class, the
        overriding method should be decorated as a `@property` method. The
        method should return an object compatible with the class
        `argparse.Namespace`, such as  when the object would be applied as
        the value `ns`, in the method:
        `argparse.ArgumentParser.parse_known_args(args, namespace=ns)`.

        The object returned from this method should provide an implementation
        of `__setattr__()`, and either or both of the `__getattr__()` and
        `__getattribute__()` methods. These methods are implemented generally
        on the class, `object`.

        The default protocol method will return the value of the
        `_option_namespace` attribute for the implementing instance, if
        defined. Otherwise, the method will return a new `argparse.Namespace`
        object. In the latter case, the namespace object will be
        initialized with no values, then stored under the
        `_option_namespace` attribute for the instance.

        Subsequent of the call to `instance.consume_args(args) -> restargs` for an
        implementing instance, the object returned from this method will be used
        to store any option values parsed from the initial `args`

        ## Advice for Implementations

        - This method utilizes a methodology of deferred initialization
          for the options namespace object.

        - The object returned from this method will be configured under
          the `consume_args()` implementation. Any default values should
          generally be provided as argument defaults, for arguments added
          within an overriding `configure_argparser()` method.

        - This method does not in itself provide any guarding for
          concurrent initialization or modification of the namespace
          object under seperate threads.

        See also:
        - `configure_argparser()`
        """
        ns = None
        if hasattr(self, "_option_namespace"):
            ns = self._option_namespace
        else:
            ns = argparse.Namespace()
            self._option_namespace = ns
        return ns

    @property
    def program_name(self) -> str:
        if hasattr(self, "_program_name"):
            return self._program_name
        else:
            name = self.__class__.__name__.lower()
            self._program_name = name
            return name

    def configure_argparser(self, parser: argparse.ArgumentParser):
        """configure an argument parser for this `Cmdline` application.

        This protocol method will be called within `consume_args()`, using
        the parser returned from the class method `init_argparser()`

        The implementing class should override this method, then adding any args,
        command subparsers, defaults, and providing other ArgumentParser configuration
        to the `parser`, within the overriding method.
        """
        pass

    def consume_args(self, args: Sequence[str]) -> (Sequence[str], argparse.ArgumentParser):
        """parse a sequence of command line arguments for this Cmdline application

        This protocol method will initialize an argument parser, calling the class method
        `init_argparser()` on the class of the implementing instance. The instance
        will be provided as an argument to the class method. The argument parser
        returned by `init_argparser()` will then be provided to the `configure_argparser()`
        instance method.

        The method `configure_argparser()` should be overidden in the implementing class.
        The overriding method  should add any command options, subcommands, and other
        configuration to the `parser` provided to `configure_argparser()`.

        This default `consume_args()` implementation will then use value of the
        `option_namespace` attribute for the instance - denoted here as `ns` -
        calling `parser.parse_known_args(args, namespace=ns)` on the initialized
        `parser`.  The list of the unparsed args will be returned. By default,
        the `parser` will be an `argparse.ArgumentParser` object.

        Any arguments parsed from the `args` will then be available as attributes to the
        object returned from the `option_namespace` property accessor. Unparsed arguments
        will be available in this method's return value.

        ## Advice for Implementations

        - Absent of any specific configuration for handling the `-h` and `--help` args,
           `argparse.ArgumentParser` by default will handle these args internally,
          typically exiting the Python process after displaying the help text for
          the argparser

        - [...]

        ## Example: Extending `consume_args()`

        (TBD)
        """
        parser = self.__class__.init_argparser(self)
        self.configure_argparser(parser)
        ## using argparse.ArgumentParser.parse_known_args()
        ## - does not err on any unrecognized args
        ## - does not parse-out any unrecognized duplicate args
        ##
        ## this will allow for any task args to be passed on
        ## to paver, when not colliding with args configured
        ## in basalt
        ##
        _, other_args = parser.parse_known_args(args, namespace=self.option_namespace)
        ## returns the list of unparsed args:
        return (other_args, parser,)

    @property
    def log_level(self) -> int:
        ## default protocol method
        return LogLevel.INFO

    @property
    def logger(self) -> logging.Logger:
        if hasattr(self, "_logger"):
            return self._logger
        else:
            ensure_log_levels()
            logger = logging.getLogger(origin_name(self.__class__))
            logger.setLevel(self.log_level)
            self.add_log_handlers(logger)
            self._logger = logger
            return logger

    def add_log_handlers(self, logger: logging.Logger):
        handler = logging.StreamHandler(stream = sys.stderr)
        datefmt = ""
        level = self.log_level
        if level < LogLevel.CRITICAL:
            datefmt = "%F %X"
        # fmt: off
        formatter = logging.Formatter('[%(process)d %(asctime)s %(thread)x] [%(levelname)s] %(message)s', datefmt=datefmt)
        # fmt: on
        handler.setFormatter(formatter)
        handler.setLevel(level)
        logger.addHandler(handler)


class HelpFormatterCls(type):
    """rudimentary metaclass for custom help formatting with argparse

    See Also
    - help_formatter_class()

    Caveats

    - The `__new__` constructor will not store the new class within
      any attribute of an existing attribute scope (e.g module, class,
      or function closure)

      If required for purpose of reference, the caller should store
      the new class as an attribute of any appropriate context object.

    - For any method added to the class within the class initializer,
      the method may not be initialized with a corresponding class
      reference cell. As such, `super()` may not function as expected,
      for any methods defined to a class within the scope of the class
      initializer.

    - Within any method that would be added within the class initializer,
      any [MRO][mro] methods may be reached from that method through
      direct reference to the class providing the method - e.g any base
      class - in lieu of super(), then providing the instance as the
     method's first arg (assuming an instance method)

    Additional Remarks

    This class was developed as part of a methodology for providing
    an arbitrary instance object to a help formatter class provied to an
    `argparse.ArgumentParser` instance. This approach has not been
    tested beyond the singleton usage case.

    [mro]: https://github.com/PacktPublishing/Metaprogramming-with-Python/blob/main/Chapter10/chapter%2010.ipynb
    """

    def __new__(
        metacls: Type[Self],
        name: str = "anonymous",
        bases: tuple = (argparse.ArgumentDefaultsHelpFormatter,),
        dct: dict = {},
        **kwargs,
    ):
        usedct: dict = dct.copy()
        ## feature: This will translate kwargs to attributes of the class,
        ## for kwargs not matching a key in the provided attributes map
        for kw in kwargs:
            if kw not in usedct:
                usedct[kw] = kwargs[kw]

        ## this will not store the class under the provided name in any module
        return super().__new__(metacls, name, bases, usedct)


def help_formatter_class(
    metaclass: type = HelpFormatterCls,
    name: str = "help_formatter",
    bases: tuple = (argparse.ArgumentDefaultsHelpFormatter,),
    dct: dict = {},
    module: Optional[ModuleArg] = None,
    **kwargs,
):
    ## pass a representative module name for the anonymous class,
    ## if no module arg was provided to this function.
    ##
    ## If the attributes dct already has a __module__ stored there,
    ## the HelpFormatterCls' initailizer will not overwrite that value.
    _mod = module if module else "<none>"
    if isinstance(module, ModuleType):
        _mod = module.__name__

    return metaclass(name, bases, dct, __module__=_mod, **kwargs)


@tasks.cmdopts([("all-tasks", "a", "Show help for all tasks")])
def help(args_help, env, describe_tasks = None):
    """
    Show task help
    Syntax: help <taskname> or help -a
    """
    ## emulating paver.tasks.help

    if 'all_tasks' in env.options.help:
        describe_tasks = env.get_tasks()

    print(args_help)
    if describe_tasks:
        for task in describe_tasks:
            task.display_help()


@tasks.cmdopts(
    [("options=", "o", "comma-separated list of options to display (default: all)")]
)
def show_options(options):
    """
    Show paver options
    """
    task_opts = options.show_options
    use_opts = None
    if hasattr(task_opts, "options"):
        use_opts = task_opts.options.split(",")
    else:
        use_opts = options.keys()
    for opt in use_opts:
        if hasattr(options, opt):
            print(opt + " = " + repr(options[opt]))
        else:
            print("Option " + opt + " not configured")


# @tasks.cmdopts([("fields=", "f", "comma-separated list of environemnt fields to display (default: all)")])
@tasks.task
def show_environment():
    """
    Show paver environment fields
    """
    envt = tasks.environment
    for name in dir(envt):
        if len(name) > 0 and name[0] != "_":
            try:
                val = getattr(envt, name)
                print(name + " = " + repr(val))
            except Exception as exc:
                # autopep8: off
                # fmt: off
                print("%s ? (Exception when accessing value: %r)" % (name, exc,))
                # autopep8: on
                # fmt: on


class CircularDependency(Exception):
    pass

class UnboundValue(ValueError):
    pass

class BoundValue(ValueError):
    pass

class ShellCommandFailed(Exception):
    pass

class ShellRunner(shellous.Runner):
    async def run_command(command, _run_future = None):
        prefix = ""
        inst = None
        try:
            inst = command.manager if isinstance(command, ShellCommand) else Basalt.instance
        except UnboundValue:
            pass
        if (inst and inst.shell_show_commands):
            prefix = os.getenv("PS4", "+ ")
            print(prefix + shlex.join(command.args))
        try:
            return await shellous.Runner.run_command(command, _run_future = _run_future)
        except Exception as exc:
            raise ShellCommandFailed() from exc


@dataclass(frozen = True)
class ShellResult(shellous.Result):
    ## TBD usage & extension @ shellous
    pass

R = TypeVar("R", bound = ShellResult)

@dataclass(frozen = True)
class ShellCommand(shellous.Command[R]):

    manager: "Optional[Basalt]"
    future: Optional[FutureType]

    def coro(self, _run_future = None):
        future = _run_future if _run_future else self.future
        return ShellRunner.run_command(self, _run_future = future)

@dataclass(frozen = True)
class ShellContext(shellous.CmdContext[R]):
    ## similar to shellous.sh
    ##
    ## an instance under Basalt will be provided to the 'sh' arg
    ## of any task providing an 'sh' arg
    ##
    manager: "Optional[Basalt]" = None
    ## ^ local back-reference to the Basalt instance

    ## used during __call__, may provide one point of extension
    shell_command_class: Type[shellous.Command] = ShellCommand

    ## utility field, referencing an enum class in shellous
    Redirect: Type[shellous.redirect.Redirect] = Redirect

    def __call__(self, *args, future: Optional[FutureType] = None, stdout = Redirect.DEFAULT, stderr = sys.stderr, stdin = None,**kwargs) -> shellous.Command[R]:
        self.manager.logger.log(LogLevel.TRACE, "new shell context call (%s): %s", self.__class__.__qualname__, args)

        inst = self
        inst = inst.stdout(stdout if stdout else Redirect.DEVNULL)
        inst = inst.stderr(stderr if stderr else Redirect.DEVNULL)
        inst = inst.stdin(stdin if stdin else Redirect.DEVNULL)

        if len(kwargs) is not int(0):
            inst = inst.set(**kwargs)

        cls = self.shell_command_class
        return cls(shellous.command.coerce(args), future = future, manager = self.manager, options = inst.options)



class Basalt(Cmdline):
    ## cmdline app class for basalt

    def stop_on_exception(self):
        return True


    @classmethod
    @property
    def instance(cls):
        if hasattr(cls, "_instance"):
            return cls._instance
        else:
            raise UnboundValue("No bound instance: %r" % cls, cls)

    @classmethod
    def bind_instance(cls, new_value: Self):
        if hasattr(cls, "_instance"):
            # fmt: off
            inst = getattr(cls, "_instance", "<missing>")
            raise BoundValue("Instance already bound: %r in %s" % (inst, cls,), inst, cls, new_value)
            # fmt: on
        else:
            cls._instance = new_value

    @property
    def shell_context(self) -> ShellContext:
        if not hasattr(self, "_shell_context"):
            ctx = ShellContext(manager = self)
            self._shell_context = ctx
        return self._shell_context

    @property
    def shell_show_commands(self) -> bool:
        if hasattr(self, "_show_shell_commands"):
            return self._show_shell_commands
        else:
            show = not self.option_namespace.quiet
            self._show_shell_commands = show
            return show

    @property
    def max_workers(self) -> int:
        ## used mainly for initializing the workers_semaphore
        return self.option_namespace.max_workers

    @property
    def log_level(self) -> int:
        if hasattr(self, "_log_level"):
            return self._log_level
        else:
            level = -1
            if self.option_namespace.quiet:
                level = LogLevel.CRITICAL
            elif self.option_namespace.verbose >= 3:
                level = LogLevel.TRACE
            elif self.option_namespace.verbose is int(2):
                level = LogLevel.DEBUG
            elif self.option_namespace.verbose is int(1):
                level = LogLevel.INFO
            else:
                level = LogLevel.WARNING
            self._log_level = level
            return level


    def __init__(self):
        ## configuration for emulating paver.tasks.main()
        environment = tasks.Environment()
        self.environment = environment

        self._runner = None
        self._exceptions = None

    @classmethod
    def init_argparser(cls, instance: Self):
        formatter_cls = basalt_help_formatter_class(instance)
        parser = argparse.ArgumentParser(
            prog=instance.program_name,
            exit_on_error=False,
            # add_help = False,
            formatter_class=formatter_cls,
        )
        conf_default = Path(".basalt", "conf.json")
        parser.add_argument(
            "--conf",
            "-c",
            dest="conf_file",
            help="Configuration file for build",
            default=conf_default,
            type=Path,
        )
        parser.add_argument(
            "--require-virtualenv",
            dest="require_virtualenv",
            help="Exit with error if not running under a virtual environment",
            default=False,
            action=ArgparseAction.STORE_TRUE,
        )
        return parser

    def configure_argparser(self, parser: argparse.ArgumentParser):
        envt = self.environment
        envt.args_parser = parser
        options = envt.options

        ##
        ## configure the arg parser
        ##
        ## the following section was transposed originally from _parse_global_options()
        ## in the module paver.tasks for paver 1.3.4, then updated for the argparse API
        ## and other features of the application in basalt
        ##
        # autopep8: off
        # fmt: off

        envt.help_function = help
        parser.add_argument('-j', '--max-workers', action=ArgparseAction.STORE,
                            help="Maximum number of conccurent tasks",
                            type = int,
                            default = len(psutil.Process().cpu_affinity()))
        parser.add_argument('-k', '--continue', action=ArgparseAction.STORE_TRUE,
                            help="Continue after erred tasks"
                            )

        parser.add_argument('-n', '--dry-run', action=ArgparseAction.STORE_TRUE,
                            help="don't actually do anything")
        ## changed: incremental verbosity
        parser.add_argument('-v', "--verbose", action=ArgparseAction.COUNT,
                            help="increase the verbosity of logging output. "
                            "Multiple values supported", default=0)
        parser.add_argument('-q', '--quiet', action=ArgparseAction.STORE_TRUE,
                            help="display only errors")
        # parser.add_argument('-h', "--help", action=ArgparseAction.STORE_TRUE,
        #                     help="display this help information.\n"
        #                     "See also: help <task_name>")
        parser.add_argument("-i", "--interactive", action=ArgparseAction.STORE_TRUE,
                            help="enable prompting")
        parser.add_argument("-f", "--file", default=envt.pavement_file,
                            help="read tasks from FILE")
        ## added: short form "-t" arg for "--propagate-traceback"
        parser.add_argument("-t", "--propagate-traceback", action=ArgparseAction.STORE_TRUE,
                            help="propagate traceback, do not hide it under BuildFailure"
                            " (for debugging)")
        parser.add_argument('-x', '--command-packages', action=ArgparseAction.STORE,
                            help="list of packages that provide distutils commands")
        # autopep8: on
        # fmt: on

    @property
    def option_namespace(self):
        ## protocol method for Cmdline args parsing
        ##
        ## here, using a common option storage onto paver
        return self.environment.options


    def running_under_virutalenv(self) -> bool:
        ## utility method for main()
        if ("VIRTUAL_ENV" in os.environ) or Path(sys.prefix, "pyvenv.cfg").exists():
            return True
        else:
            return False

    def get_dependency_order(
            # fmt: off
            self,
            task: tasks.Task,
            state: Optional[List[tasks.Task]] = None,
            cur: Optional[Union[tasks.Task, str]] = None
            # fmt: on
    ):
        ## utility method for task scheduling under main()
        if state is None:
            state = []
            cur = task
        elif cur in state:
            return
        else:
            state.append(cur)

        if isinstance(cur, str):
            cur = Basalt.instance.find_task(cur)

        needs = (Basalt.instance.find_task(id) for id in cur.needs)

        for dep in needs:
            if dep == task:
                # fmt: off
                raise CircularDependency(
                    f"Circular dependency in {task}: {task} => {task.needs}"
                )
                # fmt: on
            elif dep not in state:
                yield from self.get_dependency_order(task, state, dep)
                yield dep
                state.append(dep)

    def push_exception_info(
            # fmt: off
            self,
            task: Optional[tasks.Task],
            exc_type: Optional[Type],
            exc_args: Optional[Union[Sequence, Exception]],
            tbk: Optional[Sequence] = None
            # fmt: on
    ):
        ## store exception information
        ##
        ## The presentation of the exception information will be deferred until before
        ## return in Basalt.main()
        ##
        ## Stored values may be accessed with each_exception(), a reentrant function
        ##
        ## If `task` is null, the exception information will be interpreted
        ## as applying directly to the Basalt runtime. Else, the exception
        ## information will be interpreted relative to the denoted task.
        ##
        ## The traceback, if provided, will be displayed under the cmdline args
        ## -t/--propagate-exceptions
        emap = self._exceptions
        if not emap:
            emap = dict()
            self._exceptions = emap
        token = hash((task, exc_type, exc_args,))
        if token not in emap:
            emap[token] = (task, exc_type, exc_args, tbk)

    def each_exception(self) -> Generator[Tuple[tasks.Task, type, Tuple, Optional[List]], None, None]:
        emap = self._exceptions
        if emap:
            for data in emap.values():
                yield data


    def find_task(self, task: Union[str, tasks.Task]) -> tasks.Task:
        if isinstance(task, tasks.Task):
            return task
        else:
            rslt = self.environment.get_task(task)
            if rslt:
                return rslt
            else:
                raise ValueError("Task not found: %s" % repr(task))
    async def amain(
            self,
            run_context: RunContext,
            launch_map: TaskLaunchMap
            # run_tasks: Sequence[tasks.Task],
            # task_args: Mapping[str, Sequence[str]],
            # exit_future: FutureType
    ):

        exit_future = run_context.exit_future

        with FutureManager(
                # fmt: off
                None,  # no task at this scope
                exit_future,  # future to manage under __exit__
                self.push_exception_info,  # for exception info under __exit__
                True  # cancel the exit_future on exception
                # fmt: on
        ):

            self.logger.log(LogLevel.DEBUG, "amain")

            loop = run_context.loop
            ##
            ## process the build order from the launch_map
            run_tasks = launch_map.build_order
            nr_tasks = len(run_tasks)
            task_data = [False] * nr_tasks
            for n in range(0, nr_tasks):
                task_proxy = run_tasks[n]
                task = task_proxy.task
                taskname = task.name

                aio_task = loop.create_task(task_proxy.launch_task(), name = taskname)

                task_data[n] = (aio_task, task_proxy,)

            def cancel_aio_tasks(_):
                nonlocal task_data
                for aio_task, _ in task_data:
                    aio_task.cancel()

            exit_future.add_done_callback(cancel_aio_tasks)

            self.logger.log(LogLevel.DEBUG, "amain: gathering tasks")
            just_tasks = [False] * nr_tasks
            for n in range(0, nr_tasks):
                just_tasks[n] = task_data[n][0]
            await aio.gather(*just_tasks, return_exceptions = True)

            try:
                self.logger.log(LogLevel.DEBUG, "amain: finalizing task futures")

                duration = sys.getswitchinterval()

                for datum in task_data:

                    proxy = datum[1]
                    task = proxy.task
                    self.logger.log(LogLevel.TRACE, "awaiting run_future for %r", proxy.task)
                    run_future = proxy.run_future

                    while not run_future.done():
                        ## Implementation Note:
                        ##
                        ## This section should be not be removed.
                        ##
                        await aio.sleep(duration)

                    aio_task = datum[0]
                    try:
                        if aio_task.done() is not True:
                            self.logger.debug("Task future completed but aio task is not done, task %r (%r)", task, aio_task.done())
                            continue
                        ## try to capture any spare exceptions
                        exc = aio_task.exception()
                        if exc is not None:
                            tbk = aio_task.get_stack()
                            self.push_exception_info(proxy.task, exc.__class__, exc.args, tbk)
                    except (aio.CancelledError, cofutures.CancelledError):
                        pass

                self.logger.log(LogLevel.TRACE, "Awaited tasks")
            except Exception:
                self.push_exception_info(None, *sys.exc_info())

            if not exit_future.done():
                ## ensure that the exit fugture is given a result here
                exceptions = self._exceptions
                nr_exceptions = len(exceptions) if exceptions else 0
                exit_future.set_result(nr_exceptions)

            self.logger.log(LogLevel.TRACE, "amain return")
            return

    def main(self, args=sys.argv[1:]) -> int:
        ## handle args, then initialize & schedule tasks for  amain()

        self.bind_instance(self)

        envt = self.environment
        tasks.environment = envt
        task_args, argparser = self.consume_args(args)

        ## the user-indicated log level will not be available until
        ## after the args are parsed
        self.logger.log(LogLevel.DEBUG, "main: parsed args")

        exit_future = cofutures.Future()

        with FutureManager(
                # fmt: off
                None,
                exit_future,
                self.push_exception_info,
                True
                # fmt: on
        ):

            ## Implementation Note:
            ## the consume_args() call would normally exit when --help/-h is in args

            ##
            ## initialize and set the build order for tasks
            ##

            options = envt.options
            has_auto = False
            auto_task = None
            if options.require_virtualenv and not self.running_under_virutalenv():
                envt.error("%s: Not running under a virtual environment" % self.program_name)
                return 127
            ## referenced onto paver.tasks._launch_pavement
            ## and paver.tasks._process_commands
            pavement_f = self.load_paver_file()
            envt.pavement_file = pavement_f
            if pavement_f:
                ## load_paver_file should have initialized envt.pavement
                pavement = envt.pavement
                auto_task = getattr(pavement, "auto", None)
                has_auto = isinstance(auto_task, tasks.Task)
            to_sched = []
            to_describe = []
            task_help = False
            auto_pending = (has_auto and auto_task)
            first_loop = True
            args = task_args
            task_args_map = dict()  # syntax: Dict[str, Tuple[str]]
            ## emulating paver.tasks._process_commands()
            ## - initialize each task here, using any parsed args
            ## - note paver.tasks._parse_command_line() @ definition & usage
            ## - note paver.tasks.Environment._run_task() @ definition & usage
            while first_loop or len(args) is not int(0):
                ## by side effect, the following call may add new values
                ## to environment.options -- e.g via Task.parse_args(),
                ## subsequently Task._set_value_to_task() => sets options
                task, args = tasks._parse_command_line(args)
                if auto_pending and task and not task.no_auto and not task_help and task.shortname != "help":
                    to_sched.append(auto_task)
                    task_args_map[auto_task.name] = ()
                    auto_pending = False
                if task:
                    task_args_map[task.name] = tuple(args)
                    if task.shortname == 'help':
                        task_help = True
                        to_sched.append(task)
                        continue
                    if task_help:
                        to_describe.append(task)
                    else:
                        to_sched.append(task)
                elif first_loop and not task_help:  # when no task from args
                    task = tasks.environment.get_task('default')
                    if task:
                        task_args_map[task.name] = tuple(args)
                        to_sched.append(task)
                    else:
                        ## no tasks provided in args, no default task
                        self.logger.debug("No default task")
                        return 0
                else:
                    pass
                first_loop = False
            to_call = []

            if task_help:
                ## if 'help' is in args, then all other non-dash args will be
                ## interpreted as task names to describe under the help task,
                ## unless no other tasks are named, in which case only the
                ## 'help' task will be described
                ##
                self.environment.args_help = argparser.format_help().rstrip()
                for task in to_sched:
                    shortname = task.shortname
                    if shortname == "help" and len(to_call) is int(0):
                        to_call.append(task)
                    else:
                        to_describe.append(task)
                task_args = task_args_map[to_call[0].name]

                if len(to_describe) is int(0):
                    ## no other tasks listed - provide help only for the help task
                    to_describe = to_call

                ## setting a value to be received by the help task function
                self.environment.describe_tasks = tuple(to_describe)
                ## no further task sorting needed under 'help'
                to_sched = []

            ## expanding the build order for each task and ensuring
            ## (by side effect) no circular task deps
            ##
            rdeps_map = dict() ## str, List[str]
            deps_map = dict() ## str, List[str]
            ## - using task names in *deps_map to denote tasks, independent of
            ##   TaskProxy objects and the paver.tasks.Task contained in each
            for to_task in to_sched:
                to_name = to_task.name
                self_deps = []
                for ordered_task in self.get_dependency_order(to_task):
                    ## ensure forward/reverse dependency information is recorded here
                    ordered_name = ordered_task.name
                    self_deps.append(ordered_name)
                    rdeps_entry = rdeps_map.get(ordered_name, None)
                    if rdeps_entry:
                        rdeps_entry.append(to_name)
                    else:
                        rdeps_entry = [to_name]
                        rdeps_map[ordered_name] = rdeps_entry

                    ## avoiding duplicate task entries in the complete build map
                    ##
                    if ordered_task not in to_call:
                        to_call.append(ordered_task)
                ## ensure that the task itself is scheduled, after dependencies
                if to_task not in to_call:
                    to_call.append(to_task)
                ## lastly, add the dependency information to the deps_map
                deps_map[to_name] = self_deps

            #### return early when dry_run
            if self.option_namespace.dry_run:
                ## - paver args -n/--dry-run
                print("?? debug: dry run")
                return 0

            runner = aio.Runner()

            ## Initializing the RunContext for the amain() call
            ## - must be initialized before the TaskProxy initialization
            loop = runner.get_loop()
            workers_semaphore = aio.Semaphore(self.max_workers)
            executor = cofutures.ThreadPoolExecutor()
            run_context = RunContext(loop, exit_future, workers_semaphore, executor)

            ## the launch_map will be used to contain the build order, under a
            ## cancellable structure
            launch_map = TaskLaunchMap(run_context)

            for to_task in to_call:
                tskname = to_task.name
                deps_data = deps_map.get(tskname, ())
                rdeps_data = rdeps_map.get(tskname, ())
                launch_map.create_task_proxy(to_task, self, run_context, deps_data, rdeps_data)

            launch_map.finalize()

            ##
            ## set signal handlers
            ##
            def cancel_main(*_):
                nonlocal exit_future, launch_map
                print()
                self.logger.debug("Cancelling")
                exit_future.cancel()
                launch_map.cancel()

            sigvars = vars(nsig.Signals).keys()
            int_handler = SigContext.activate(nsig.SIGINT, cancel_main)
            loop.add_signal_handler(nsig.SIGINT, cancel_main, nsig.SIGINT)
            term_handler = SigContext.activate(nsig.SIGTERM, cancel_main)
            loop.add_signal_handler(nsig.SIGTERM, cancel_main, nsig.SIGTERM)
            quit_handler = None
            hup_handler = None
            if 'SIGQUIT' in sigvars:
                quit_handler = SigContext.activate(nsig.SIGQUIT, cancel_main)
                loop.add_signal_handler(nsig.SIGQUIT, cancel_main, nsig.SIGQUIT)
            if 'SIGHUP' in sigvars:
                hup_handler = SigContext.activate(nsig.SIGHUP, cancel_main)
                loop.add_signal_handler(nsig.SIGHUP, cancel_main, nsig.SIGHUP)


            ## blocking on the async amain call, by way of thread.join
            ##
            ## this also ensures that the task loop can be started
            ## and provided with the amain coroutine via Runner.run,
            ## regardless of whether there's any loop running in the
            ## current thread

            self.logger.log(LogLevel.DEBUG, "main: dispatching to amain")

            try:
                coro = self.amain(run_context, launch_map)
                thr = threading.Thread(target = runner.run, args=(coro,))
                thr.start()
                thr.join()
            finally:
                int_handler.restore()
                term_handler.restore()
                if quit_handler:
                    quit_handler.restore()
                if hup_handler:
                    hup_handler.restore()

        exc = None
        if not exit_future.done():
            exit_future.set_result(0)
        elif not exit_future.cancelled():
            exc = exit_future.exception()

        # this assumes amain() or some other call will have logged
        # any exception info for an exception received by the
        # exit future
        rc = 0 if exc is None else 1

        ##
        ## process any deferred exception info
        ##

        show_tbk = self.option_namespace.propagate_traceback
        for datum in self.each_exception():
            (task, etype, eargs, etbk) = datum
            rc = rc + 1 if rc < 256 else rc

            if task:
                sys.stderr.write("Task error: %s: " % task.name)
            else:
                sys.stderr.write("Error: ")
            # fmt: off
            if isinstance(etype, type):
                ## try to avoid redundant presentation of the execption type
                if not (isinstance(etype, type) and isinstance(eargs, etype)):
                    sys.stderr.write(etype.__qualname__)
            if eargs:
                if isinstance(eargs, Sequence):
                    ## expand any arg sequence into a string
                    sys.stderr.write("(")
                    sys.stderr.write(", ".join(repr(arg) for arg in eargs))
                    sys.stderr.write(")")
                    print(file = sys.stderr)
                else:
                    print(repr(eargs), file = sys.stderr)
            else:
                print(file = sys.stderr)
            # fmt: on

            if etbk and show_tbk:
                print("-- Traceback", file = sys.stderr)
                if isinstance(etbk, list):
                    for item in etbk:
                        print(repr(item), file = sys.stderr)
                elif isinstance(etbk, TracebackType):
                    traceback.print_tb(etbk, file = sys.stderr)
                else:
                    print(repr(etbk))

            ## end of amain
            return rc

    def get_resident_tasks(self) -> dict[str, tasks.Task]:
        ## return a dict of resident tasks for this paver extension
        ##
        ## these tasks should each be implemented somewhere within
        ## the extension runtime, typically under a @task decorator
        return {
            "help": help,  # partly shadowing paver.tasks.help
            "show_options": show_options,
            "show_environment": show_environment,
            ## Paver tasks:
            "generate_setup": misctasks.generate_setup,
            "minilib": misctasks.minilib,
        }

    def load_paver_file(self) -> Optional[PathArg]:
        ## emulating behaviors from paver.tasks._launch_pavement()
        ##
        ## usage:
        ## - for task enumeration under the 'help' handling here
        ## - for normal evaluation of the paver file under main()
        envt = self.environment
        file = self.option_namespace.file
        if envt.pavement:
            return getattr(envt.pavement, "__file__", None)
        exists = os.path.exists(file)
        if not exists:
            return

        mod = ModuleType(Path(file).stem)
        envt.pavement = mod
        mod.__file__ = file
        source = None
        if exists:
            with open(file, mode="r") as io:
                source = io.read()
            exec(compile(source, file, "exec"), mod.__dict__)
        resident_tasks = self.get_resident_tasks()
        for tsk in resident_tasks:
            if not hasattr(mod, tsk):
                setattr(mod, tsk, resident_tasks[tsk])
        return file if exists else None


class BasaltHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def format_help(self):
        instance = self.prog
        ## args_str: the help text from the superclass' help formatter
        args_str = super().format_help().strip()

        ##
        ## emulating paver.tasks.help()
        ##
        ## splicing the paver task help onto the args_str,
        ## an argparse help string
        ##
        ## loading the paver file first, under help formatting
        file = instance.load_paver_file()
        environment = instance.environment
        task_list = environment.get_tasks()
        if len(task_list) == 0:
            ## should not be reached
            ##
            ## get_tasks() should be able to access at least the list
            ## of tasks added after Basalt.get_resident_tasks(), called
            ## during load_paver_file()
            ##
            environment.error(
                "%s: no tasks found",
                instance.program_name,
                file,
            )
            return args_str
        ## referenced onto paver tasks.py, with local adaptations
        ## for integrating with argparse
        task_list = sorted(task_list, key=lambda task: task.name)
        maxlen, task_list = tasks._group_by_module(task_list)
        out = StringIO()
        print(args_str, file=out)
        fmt = "  %-" + str(maxlen) + "s - %s"
        for group_name, group in task_list:
            print("\nTasks from %s:" % (group_name), file=out)
            for task in group:
                if not getattr(task, "no_help", False):
                    print(fmt % (task.shortname, task.description), file=out)
        return out.getvalue()


def basalt_help_formatter_class(
    instance: Basalt,
    metacls: type = HelpFormatterCls,
    name: str = "basalt_help_formatter",
    bases: tuple = (BasaltHelpFormatter,),
    dct: dict = {},
    **args,
):
    ## Through a sort of indirection, this defines a help formatter
    ## for the Basalt layer on paver, here using argparser.
    ##
    ## The format_help method on the resulting class should have access
    ## to any program instance data, e.g when enumerating paver tasks
    ## for the help text.
    ##
    ## argparse accepts a formatter class, and not a formatter object
    ## at Python 3.11. This provides something of a workaround, in the
    ## form of an anonumous class metaobject having some instance access,
    ## using Python metaclasses and a functional API.
    ##
    ## The main mechanism of the help formatter has been implemented
    ## in format_help on BasaltHelpFormatter.
    ##
    ## This function operates to ensure a 'prog' attribute will be available
    ## on the single-use BasaltHelpFormatter subclass, there storing the
    ## program for the help formatter.

    merge_dct = False

    if "prog" not in dct and "prog" not in args:
        merge_dct = dict(prog = instance)

    dct.update(merge_dct)

    ## call upwards in the function chain ...
    rslt = help_formatter_class(metacls, name, bases, dct, **args)

    return rslt


## FIXME tmp function for purpose of testing only ...
## FIXME see https://ipython.readthedocs.io/en/stable/config/eventloops.html
def running_ipython() -> Optional[bool]:
    if "IPython" in sys.modules:
        return sys.modules["IPython"].Application.initialized()


## FIXME ... it will always be "__main__" here
if __name__ == "__main__" and not running_ipython():
    sys.exit(Basalt().main(sys.argv[1:]))
