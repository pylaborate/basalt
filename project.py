#!/usr/bin/env python3
##
## project.py - basalt
##
## Usage
## - general shell command tooling via the project Makefile
## - for command usage, run as e.g `python3 project.py --help`
##
## Goals
## - Implement a shell tool providing support for boostrap installation
##   of a virtual environment using the virtualenv provider, while
##   utilizing packages available in a Python 3 distribution
##
## - Avoid requiring that virtualenv would be installed under the
##   destination virtual environment
##
## Limitations
## - For purposes of project boostrapping, this code is limited to
##   packages avaialble in Python stdlib
##
## - Tested with Python versions 3.7 and subsequent

import argparse as ap
from contextlib import contextmanager
import os
import re
import shlex
from subprocess import Popen
import sys
from tempfile import TemporaryDirectory


from typing import Any, Callable, Generator, Sequence, Type, TypeVar

if sys.version_info >= (3, 10):
    from typing import TypeAlias

import venv


def notify(fmt: str, *args):
    ## utility method for user notification during cmd exec
    print("#-- " + fmt % args, file=sys.stderr)


def with_main(
    options: ap.Namespace,
    sub_main: "Callable",
    sys_args: "Sequence[str]" = (),
    main_args=(),
    main_kwargs=None,
):
    ## trivial hack for running something like a shell command
    ## within the same python process as the caller, given a
    ## known 'main' function for the effective shell command
    ## implementation
    ##
    ## This is used, below, to ensure that the initial venv
    ## environment will be created with the same Python
    ## implementation as the running Pythyon process
    rc = 1
    arg_0 = options.prog
    orig_argv = sys.argv
    sub_name = "<Unknown>"
    try:
        sub_name = "%s.%s" % (
            sub_main.__module__,
            sub_main.__name__,
        )
    finally:
        pass
    try:
        if options.debug:
            notify("Running %s", sub_name)
        # fmt: off
        sys.argv = [arg_0, *sys_args]
        sub_rtn = None
        if main_kwargs:
            sub_rtn = sub_main(*main_args, **main_kwargs)
        else:
            sub_rtn = sub_main(*main_args)
        # fmt: on
        if isinstance(sub_rtn, int):
            rc = sub_rtn
        else:
            rc = 0
    except Exception as e:
        notify("Failed call to %s: %s", sub_name, e)
    finally:
        if options.debug:
            notify("Returning from %s: %d", sub_name, rc)
        sys.argv = orig_argv
        return rc


def guess_env_scripts_dir(env_dir: str) -> str:
    ## Return an effective guess about the location of the scripts or 'bin'
    ## subdirectory of the provided env_dir.
    ##
    ## This assumes that all Python virtual environment providers would use
    ## essentially the same scripts subdirectory name - possibly differing
    ## in character case, on operating systems utilizing a case-folding
    ## syntax in filesystem pathnames
    ##
    if sys.platform == "win32":
        ## referenced onto venv ___init__.py, Python 3.9
        return os.path.join(env_dir, "Scripts")
    else:
        return os.path.join(env_dir, "bin")


def ensure_env(options: ap.Namespace) -> int:
    ## ensure that a virtualenv virtual environment exists, or will have been
    ## created, at a pathname indicated in the provided argument options.
    ##
    ## By default, the primary virtual environment would use the same Python
    ## implementation as that in which this project.py script is running.
    ## This behavior may be modified by providing the args '--python "<path>"'
    ## using the --virtualenv-opts option of the 'ensure_env" cmd for this
    ## project.py
    ##
    ## If a virtual environment exists at the env_dir specified in `options``:
    ## - returns a non-zero integer if the env_dir exists but does not appear to
    ##   comprise a virtualenv virtual environment, i.e if no bin/activate_this.py
    ##   exists within the env_dir
    ## - otherwise returns 0
    ##
    ## On success, a virtualenv virtual environment will have been installed
    ## at the env_dir pathname provided in `options`
    do_debug = options.debug

    env_dir = os.path.abspath(options.env_dir)
    env_cfg = os.path.join(env_dir, "pyvenv.cfg")
    if os.path.exists(env_cfg):
        scripts_dir = guess_env_scripts_dir(env_dir)
        py_activate = os.path.join(scripts_dir, "activate_this.py")
        if os.path.exists(py_activate):
            notify("Virtual environment already created: %s", env_dir)
            return 0
        else:
            # fmt: off
            notify("Virtual environment exists but bin/activate_this.py not found: %s",
                   env_dir)
            # fmt: on
            return 7
    else:
        rc = 1
        with TemporaryDirectory(
            prefix=options.prog + ".", dir=options.tmpdir
        ) as tmpenv_dir:
            notify("Creating bootstrap venv %s", tmpenv_dir)
            if sys.version_info.major >= 3 and sys.version_info.minor >= 9:
                main_args = ("--upgrade-deps", tmpenv_dir)
            else:
                main_args = (tmpenv_dir,)  # type: ignore
            try:
                # fmt: off
                rc = with_main(options, venv.main, main_args= (main_args,))
                # fmt: on
            except Exception as exc:
                notify("bootstrap venv creation failed: %s", exc)
                return rc
            else:
                if rc != 0:
                    notify("bootstrap venv creation failed")
                    return rc
            pip_install_opts = options.pip_install_opts
            tmp_scripts_dir = guess_env_scripts_dir(tmpenv_dir)
            pip_cmd = os.path.join(tmp_scripts_dir, "pip")
            rc = 11
            notify("Installing virtualenv in bootstrap venv")
            pip_install_argv = [pip_cmd, "install", *pip_install_opts, "virtualenv"]
            if do_debug:
                notify("running subprocess: " + shlex.join(pip_install_argv))
            try:
                with Popen(
                    pip_install_argv,
                    stdin=sys.stdin,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                ) as proc:
                    proc.wait()
                    rc = proc.returncode
            except Exception as e:
                notify("Failed to create primary virtual environment: %s", e)
                return 23
            if rc != 0:
                notify("Failed to install virtualenv, pip install exited %d", rc)
                return rc
            ## now run vitualenv to create the actual virtualenv
            env_dir = options.env_dir
            virtualenv_cmd = os.path.join(tmpenv_dir, tmp_scripts_dir, "virtualenv")
            virtualenv_opts = options.virtualenv_opts
            notify("Creating primary virtual environment in %s", env_dir)
            virtualenv_argv = [virtualenv_cmd, *virtualenv_opts, env_dir]
            if do_debug:
                notify("running subprocess: " + shlex.join(virtualenv_argv))
            try:
                with Popen(
                    virtualenv_argv,
                    stdin=sys.stdin,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                ) as proc:
                    proc.wait()
                    rc = proc.returncode
                if rc != 0:
                    notify("virtualenv command exited non-zero: %d", rc)
                return rc
            except Exception as e:
                notify("Failed to create primary virtual environment: %s", e)
                return 31
            finally:
                notify("Removing bootstrap venv %s", tmpenv_dir)


def run_ensure_env(options: ap.Namespace) -> int:
    ## wrapper onto ensure_env()
    verbosity = options.verbose
    do_notify = verbosity >= 1
    if not options.debug:
        options.debug = verbosity >= 2
    do_debug = options.debug
    if do_notify:
        if "-v" not in options.pip_install_opts:
            for n in range(0, verbosity):
                options.pip_install_opts.append("-v")
        if "-v" not in options.virtualenv_opts:
            for n in range(0, verbosity):
                options.virtualenv_opts.append("-v")
    tmpdir = options.tmpdir
    if tmpdir is not None:
        ## ensure uniform specification for tmpdir w/i this process
        ## and subprocesses
        orig_umask = os.umask(0o077)
        try:
            if not os.path.exists(tmpdir):
                if do_debug:
                    notify("Creating temporary directory with umask 0o077: %s", tmpdir)
                os.makedirs(tmpdir)
        finally:
            os.umask(orig_umask)
        os.environ["TMPDIR"] = tmpdir
    return ensure_env(options)


T = TypeVar("T")
if sys.version_info >= (3, 10):
    Yields: TypeAlias = Generator[T, None, None]
    OptionsFunc: TypeAlias = Callable[[ap.Namespace], Any]
else:
    Yields = Generator[T, None, None]  # type: ignore
    OptionsFunc = Callable[[ap.Namespace], Any]  # type: ignore


def show_help_func(parser: ap.ArgumentParser, stream=sys.stdout) -> OptionsFunc:
    def wrapped_show_help(options: ap.Namespace):
        nonlocal parser, stream
        parser.print_help(file=stream)

    return wrapped_show_help


@contextmanager
def argparser(
    prog,
    formatter_class: "Type[ap.HelpFormatter]" = ap.ArgumentDefaultsHelpFormatter,
    **kwargs,
) -> Yields[ap.ArgumentParser]:
    parser = ap.ArgumentParser(prog=prog, formatter_class=formatter_class, **kwargs)
    yield parser


@contextmanager
def command_parser(
    subparser: ap._SubParsersAction,
    name: str,
    func: OptionsFunc,
    description: str,
    formatter_class: "Type[ap.HelpFormatter]" = ap.ArgumentDefaultsHelpFormatter,
    **parser_args,
) -> "Yields[ap.ArgumentParser]":
    helper_args = {}
    if "help" not in parser_args:
        ## include the first line from the command desciption as the help text
        ## for the command when listed under `project.py -h`
        helper_args["help"] = re.split("[\n\r]", description)[0]

    cmd_parser = subparser.add_parser(
        name,
        formatter_class=formatter_class,
        description=description,
        **helper_args,  # type: ignore
        **parser_args,
    )
    cmd_parser.set_defaults(func=func)
    yield cmd_parser


@contextmanager
def subparsers(
    root_parser: ap.ArgumentParser,
    title="commands",
    help="Available commands. See <command> -h",
    **kwargs,
) -> Yields[ap._SubParsersAction]:
    yield root_parser.add_subparsers(title=title, help=help, **kwargs)


def add_common_args(parser: ap.ArgumentParser):
    ## add common args - towards ensuring that these args will be
    ## available as args before and after the ensure_env command name
    parser.add_argument(
        "--tmpdir",
        "-t",
        help="Temporary directory for commands. " "If None, use system default",
        default=os.environ.get("TMPDIR", None),
    )
    parser.add_argument(
        "--verbose",
        "-v",
        help="Increase verbosity (cumulative)",
        default=0,
        action="count",
    )


def get_argparser(**parser_kwargs):
    with argparser(**parser_kwargs) as mainparser:
        if "prog" in parser_kwargs:
            ## using arg options for shared storage of the program name
            mainparser.set_defaults(
                prog=parser_kwargs["prog"],
            )
        mainparser.add_argument(
            "--debug",
            "-d",
            help="Run with debugging messages enabled (equivalent to -vv)",
            default=False,
            action="store_true",
        )
        add_common_args(mainparser)
        with subparsers(mainparser) as subparser:
            with command_parser(
                subparser,
                "ensure_env",
                run_ensure_env,
                description="Ensure that a virtual environment is created",
            ) as mkenv_parser:
                mkenv_parser.add_argument(
                    "--pip-opt",
                    "-i",
                    help="Cumulative options to pass to pip install",
                    default=[],
                    action="append",
                    dest="pip_install_opts",
                )
                ## ensure e.g "-v" and "--tmpdir" are avaialble as args,
                ## before and after the 'ensure_env' cmd name in argv
                add_common_args(mkenv_parser)
                mkenv_parser.add_argument(
                    "env_dir",
                    help="Directory path for virtual environment",
                    default="env",
                    nargs="?",
                )
    return mainparser


def running_ipython() -> bool:
    if "IPython" in sys.modules:
        return sys.modules["IPython"].Application.initialized()
    else:
        return False


if __name__ == "__main__" and not running_ipython():
    this_file = os.path.abspath(__file__)
    this = os.path.basename(this_file)
    project = os.path.basename(os.path.dirname(this_file))

    mainparser = get_argparser(
        prog=this, description="Project tools for %s" % project
    )

    cmd_args = sys.argv[1:]
    # options = mainparser.parse_args(cmd_args)
    options = ap.Namespace()
    mainparser.parse_args(cmd_args, options)

    _env = os.environ.get("VIRTUALENV_OPTS", None)
    options.virtualenv_opts = shlex.split(_env) if _env else ()

    _env = os.environ.get("PIP_INSTALL_OPTS", None)
    options.pip_install_opts = shlex.split(_env) if _env else ()

    if "func" in options:
        rc = options.func(options)
        if isinstance(rc, int):
            sys.exit(rc)
        else:
            sys.exit(0)
    else:
        ## args but no command was specified in cmd_args
        mainparser.print_help(file=sys.stdout)
        sys.exit(1)
