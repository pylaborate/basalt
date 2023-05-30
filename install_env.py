#!/usr/bin/env python3

## installation script for creating a Python virtual environment
##
## Usage: ./install_env.py -h ...
##
## If env_dir is provided to this script, the environment
## will be created in that directory.
##
## By default, the environment will be created in the 'env' subdir
## of the directory where this script is installed
##
## If the environment variable VENV_PROMPT is defined, that string
## will be used as the prompt for the virtual environment. The
## default prompt is derived from the basename of the directory
## where this file is located

import argparse as ap
import multiprocessing as mp
import os
from pathlib import Path
import sys
from typing import Any, Callable, List, Sequence, Literal, Optional
import venv

import shlex
from tempfile import TemporaryDirectory
from argparse import Namespace
from venv import main as venvmain
from subprocess import Popen


THIS: Path = Path(__file__).absolute()
PROG: str = str(THIS.name)


def notify(fmt: str, *args: List[Any]):
    # fmt: off
    print("#-- " + PROG + ": " + fmt % args, file = sys.stderr)
    # fmt: on


def running_ipython() -> Optional[bool]:
    if sys.modules.get("IPython", False):
        # fmt: off
        try:
            return sys.modules["IPython"].Application.initialized()
        except Exception as exc:
            notify("Exception while testing for IPython: %r", exc)
            return False
        # fmt: on


def gen_argparser(prog: str) -> ap.ArgumentParser:
    # fmt: off
    prog = prog if prog else os.path.basename(__file__ if running_ipython() else sys.argv[0])
    parser = ap.ArgumentParser(prog = prog, formatter_class=ap.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--prompt", "-p", help="Prompt for virtual environment",
                        default = "env")
    parser.add_argument("env_dir", help="Base directory for virtual environment",
                        default = "env", nargs="?")
    # fmt: on
    return parser


def with_main(
    options: ap.Namespace,
    sub_main: "Callable",
    sys_args: "Sequence[str]" =(),
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


# fmt: off
def run_venv(basedir: (Path | str),
             prompt: (Literal[False] | str) = False,
             upgrade: bool = False):
    ## partial functional interface for venv
    args = []
    if prompt:
        args.append("--prompt")
        args.append(str(prompt))
    if upgrade:
        args.append("--upgrade-deps")
    args.append(str(basedir))
    notify("Creating virtual environment %s => %s", prompt, basedir)
    rc = 0
    try:
        venv.main(args)
    except Exception as exc:
        notify("Error when creating virtual environent: %r", exc)
        rc = 1
    sys.exit(rc)
# fmt: on


def ensure_env(ns: Namespace):

    ## ensure that a virtualenv virtual environment exists at a path provided
    ## under the configuration namespace 'ns'
    ##
    ## For purposes of project bootstrapping, this workflow proceeds as follows:
    ## 1) Creates a bootstrap pip environment using venv in this Python process
    ## 2) Installs the virtualenv package with pip, in that environment
    ## 3) Creates the primary virtual environment using virtualenv from within
    ##    the bootstrap pip environment
    ##
    ## By default, the primary virtual environment would use the same Python
    ## implementation as that running this project.py script. This behavior
    ## may be modified by providing --python "<path>" within the
    ## --virtualenv-opts option to this project.py script.
    ##
    ## If a virtual environment exists at the provided envdir:
    ## - Exits non-zero if it does not appear to comprise a virtualenv virtual
    ##   environment, i.e if no bin/activate_this.py exists within envdir
    ## - Else, exits zero for the existing environment
    ##
    ## On success, a virtualenv virtual environment will have been installed
    ## at the envdir provided in 'ns'.
    envdir = ns.envdir
    env_cfg = os.path.join(envdir, "pyvenv.cfg")
    if os.path.exists(env_cfg):
        py_activate = os.path.join(envdir, "bin", "activate_this.py")
        if os.path.exists(py_activate):
            notify("Virtual environment already created: %s", envdir)
            sys.exit(0)
        else:
            notify(
                "Virtual environment exists but bin/activate_this.py not found: %s",
                envdir,
            )
            sys.exit(7)
    else:
        with TemporaryDirectory(prefix=ns.__this__ + ".", dir=ns.tmpdir) as tmp:
            venv_args = ["--upgrade-deps", tmp]
            notify("Creating bootstrap venv environment %s", tmp)
            with_main(ns, venvmain, venv_args, "bootstrap venv creation failed: %s")
            notify("Installing virtualenv in bootstrap environment %s", tmp)
            pip_opts = shlex.split(ns.pip_opts)
            pip_cmd = os.path.join(tmp, "bin", "pip")
            pip_install_argv = [pip_cmd, "install", *pip_opts, "virtualenv"]
            rc = 11
            try:
                proc = Popen(
                    pip_install_argv,
                    stdin=sys.stdin,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                )
                proc.wait()
                rc = proc.returncode
            except Exception as e:
                notify("Failed to create primary virtual environment: %s", e)
                sys.exit(23)
            if rc != 0:
                notify("Failed to install virtualenv, pip install exited %d", rc)
                sys.exit(rc)
            ## now run vitualenv to create the actual virtualenv
            envdir = ns.envdir
            # fmt: off
            notify("Creating primary virtual environment in %s", envdir)
            virtualenv_cmd = os.path.join(tmp, "bin", "virtualenv")
            virtualenv_opts = shlex.split(ns.virtualenv_opts)
            virtualenv_argv = [virtualenv_cmd, *virtualenv_opts, envdir]
            try:
                ## final subprocess call - this could be managed via exec
                proc = Popen(virtualenv_argv,
                             stdin = sys.stdin, stdout = sys.stdout,
                             stderr = sys.stderr)
                proc.wait()
                rc = proc.returncode
                if (rc != 0):
                    notify("virtualenv command exited non-zero: %d", rc)
                else:
                    notify("Created virtualenv environment in %s", envdir)
                notify("Removing bootstrap venv environment %s", tmp)
                sys.exit(rc)
            except Exception as e:
                notify("Failed to create primary virtual environment: %s", e)
                sys.exit(31)


if __name__ == "__main__" and not running_ipython():
    ## run python in a subprocess, to create a virtual env
    rc = 1
    parser = gen_argparser(PROG)
    options = parser.parse_args(sys.argv[1:])
    env_dir = str(options.env_dir)
    env_cfg = Path(env_dir, "pyvenv.cfg")
    if env_cfg.exists():
        # fmt: off
        notify("Virtual environment already created in %s. File exists: %s", env_dir, env_cfg)
        # fmt: on
        sys.exit(rc)
    try:
        ## spawning a new process, in lieu of calling venv as a shell script
        mp.set_start_method("spawn")
        mp.log_to_stderr()
        # fmt: off
        p = mp.Process(target=run_venv, args=(env_dir, options.prompt, True))
        # fmt: on
        p.start()
        p.join()
        rc = 0
    except Exception as e:
        notify("Error: %s" % e)
    sys.exit(rc)
