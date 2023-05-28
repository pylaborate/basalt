## pylaborarte.basalt.__main__

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from io import StringIO
import os
from pathlib import Path
import paver.misctasks as misctasks
import paver.tasks as tasks
import sys
from types import ModuleType
from typing import Collection, Generator, List, Optional, Self, Sequence, Type


class ArgparseAction(StrEnum):
    STORE = "store"
    STORE_CONST = "store_const"
    STORE_TRUE = "store_true"
    STORE_FALSE = "store_false"
    APPEND = "append"
    APPEND_CONST = "append_const"
    COUNT = "count"
    HELP = "help"
    VERSION = "version"
    EXTEND = "extend"


@dataclass(init=False, eq=False, order=False)
class Cmdline:

    ## instance fields
    argparser: argparse.ArgumentParser

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
        progname = os.path.basename(sys.argv[0])
        return argparse.ArgumentParser(prog=progname)

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

    def configure_argparser(self, parser: argparse.ArgumentParser):
        """configure an argument parser for this `Cmdline` application.

        This protocol method will be called within `consume_args()`, using
        the parser returned from the class method `init_argparser()`

        The implementing class should override this method, then adding
        args and other configuration to the `parser` within the overriding
        method.
        """
        pass

    @contextmanager
    ## FIXME with the @contextmanager implementation for consume_args
    ## all implementations must call consume_args as a context manager
    def consume_args(self, args: Sequence[str]) -> Generator[List[str], None, None]:
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
        yield other_args
        ## TBD lock the options namespace from further modification:
        # self.option_namespace.configured()


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
    module: Optional[ModuleType | str] = None,
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


@tasks.task
def help(args_help, describe_tasks, options):
    """
    Show task help
    Syntax: help <taskname>
    """
    ## emulating paver.tasks.help()
    if describe_tasks:
        for task in describe_tasks:
            task.display_help()
        ## exit to prevent paver from running any of the named tasks
        sys.exit(0)
    else:
        out = sys.stderr
        print(args_help, file=out)


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
    Show paver environemnt fields
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


class Basalt(Cmdline):
    ## cmdline app class for basalt

    def __init__(self):
        ## configuration for emulating paver.tasks.main()
        environment = tasks.Environment()
        self.environment = environment
        ## ensure the environment will be avaialble as a parameter for tasks
        environment.environment = environment
        ## configuration for basalt tasklib => *_conf_* tasks
        environment.option_storage_skip = ["prog"]

    @classmethod
    def init_argparser(cls, instance: Self):
        formatter_cls = basalt_help_formatter_class(instance)
        parser = argparse.ArgumentParser(
            prog="basalt",
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
        options.prog = parser.prog
        ## set defualt options
        if not hasattr(options, "require_virtualenv"):
            options.require_virtualenv = False

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
        parser.add_argument('-n', '--dry-run', action=ArgparseAction.STORE_TRUE,
                            help="don't actually do anything")
        parser.add_argument('-v', "--verbose", action=ArgparseAction.STORE_TRUE,
                            help="display all logging output")
        parser.add_argument('-q', '--quiet', action=ArgparseAction.STORE_TRUE,
                            help="display only errors")
        # parser.add_argument('-h', "--help", action=ArgparseAction.STORE_TRUE,
        #                     help="display this help information.\n"
        #                     "See also: help <task_name>")
        parser.add_argument("-i", "--interactive", action=ArgparseAction.STORE_TRUE,
                            help="enable prompting")
        parser.add_argument("-f", "--file", default=envt.pavement_file,
                            help="read tasks from FILE")
        parser.add_argument("--propagate-traceback", action=ArgparseAction.STORE_TRUE,
                            help="propagate traceback, do not hide it under BuildFailure"
                            " (for debugging)",)
        parser.add_argument('-x', '--command-packages', action=ArgparseAction.STORE,
                            help="list of packages that provide distutils commands")
        # autopep8: on
        # fmt: on

    @contextmanager
    def consume_args(self, args: Collection[str]):
        with super().consume_args(args) as restargs:
            if ("help" in restargs) or ("basalt_help" in restargs):
                ## one approach that produces a help string, here ...
                ##
                ## This sets a few scoped values into the instance environment,
                ## to be used from other methods
                task_desc = len(restargs) != 0
                new_parser = self.init_argparser(self)
                self.configure_argparser(new_parser)
                if not task_desc:
                    ## argparser takes over here, then exits after it prints the help text:
                    new_parser.parse_known_args(["-h"])
                self.environment.args_help = new_parser.format_help().strip()
                describe_tasks = False
                if task_desc:
                    to_desc = []
                    for name in restargs:
                        if name == "help":
                            continue
                        task = self.environment.get_task(name)
                        if task:
                            to_desc.append(task)
                        else:
                            print("[help] Task not found: %s" % (name), file=sys.stderr)
                            sys.exit(1)
                    describe_tasks = to_desc
                self.environment.describe_tasks = describe_tasks

            yield restargs

    @property
    def option_namespace(self):
        ## protocol method for Cmdline args parsing
        return self.environment.options

    def get_option(self, name, *args):
        ## retrieve an option, as set via cmdline args or other means
        options = self.environment.options
        if hasattr(options, name):
            return getattr(options, name)
        else:
            nargs = len(args)
            if nargs == 0:
                raise KeyError("No option found: " + repr(name), name)
            elif nargs == 1:
                return args[0]
            else:
                return args

    def running_under_virutalenv(self) -> bool:
        ## utility method for main()
        if ("VIRTUAL_ENV" in os.environ) or Path(sys.prefix, "pyvenv.cfg").exists():
            return True
        else:
            return False

    def main(self, args=sys.argv[1:]) -> int:
        envt = self.environment
        tasks.environment = envt
        with self.consume_args(args) as task_args:
            options = envt.options
            has_auto = False
            if options.require_virtualenv and not self.running_under_virutalenv():
                envt.error("%r: Not running under a virtual environment" % options.prog)
                return 127
            try:
                pavement_f = self.load_paver_file()
                envt.pavement_file = pavement_f
                if pavement_f:
                    ## load_paver_file should have initialized envt.pavement
                    pavement = envt.pavement
                    ## referenced onto paver.tasks._launch_pavement
                    ## and paver.tasks._process_commands
                    auto_task = getattr(pavement, "auto", None)
                    has_auto = isinstance(auto_task, tasks.Task)
                tasks._process_commands(task_args, auto_pending=has_auto)
                return 0

            except Exception:
                ## emulating paver.tasks.main
                info = sys.exc_info()[1]
                envt.error("Build failed: %s", info)
                return 1

    def get_resident_tasks(self) -> dict[str, tasks.Task]:
        ## return a dict of resident tasks for this paver extension
        ##
        ## these tasks should each be implemented somewhere within
        ## the extension runtime, typically under the @task decorator
        return {
            "help": help,  # originally: paver.tasks.help
            "show_options": show_options,
            "show_environment": show_environment,
            "generate_setup": misctasks.generate_setup,
            "minilib": misctasks.minilib,
        }

    def load_paver_file(self) -> Optional[Path | str]:
        ## emulating behaviors from paver.tasks._launch_pavement()
        ##
        ## usage:
        ## - for task enumeration under the 'help' handling here
        envt = self.environment
        file = self.get_option("file", envt.pavement_file)
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

class BasaltHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):

        instance = self.prog
        ## args_str: the help text from the superclass' help formatter
        args_str = super().format_help().strip()

        ##
        ## emulating the behaviors of paver.tasks.help()
        ## onto an argparse help semantics
        ##
        file = instance.load_paver_file()
        environment = instance.environment
        task_list = environment.get_tasks()
        if len(task_list) == 0:
            ## should not be reached
            ##
            ## may cause secondary errors if this would be reached
            ## and not caught here
            ##
            ## if reached, there's probably been an error under load_paver_file
            ##
            ## load_paver_file and the paver sources it's referenced on would define
            ## a number of built-in tasks for the paver environment. At least those
            ## resident tasks should be returned in the task list
            environment.error(
                "%s: no tasks discovered in %s",
                instance.get_option("prog", __name__),
                file,
            )
            return args_str
        ## sourced on paver tasks.py, with local adaptations
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

    local_dct = False

    if "prog" not in dct and "prog" not in args:
        if not local_dct:
            dct = dct.copy()
            local_dct = True
        dct["prog"] = instance

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
