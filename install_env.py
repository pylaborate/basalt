#!/usr/bin/env python3

## installation script for creating a Python virtual environment
##
## Usage: ./install_env.py [env_dir]
##
## If env_dir is provided to this script, the environment
## will be created in that directory.
##
## By default, the environment will be created in the 'env' subdir
## of the directory where this script is installed
##
## If the environment variable VENV_PROMPT is defined, that string
## will be used as the prompt for the virtual environment. The
## default prompt for this project is "basalt"

import sys
import os
from pathlib import Path
from typing import List, Literal, Any

import multiprocessing as mp
import venv

PROMPT_DEFAULT : str = "basalt"

def notify(fmt: str, *args: List[Any]):
    print("#-- " + fmt, *args, file = sys.stderr)

def mk_venv(basedir: (Path | str),
            prompt: (Literal[False] | str) = False,
            upgrade: bool = False):
    ## partial functional interface for venv
    args = list()
    if prompt:
        args.append("--prompt")
        args.append(str(prompt))
    if upgrade:
        args.append("--upgrade-deps")
    args.append(str(basedir))
    notify("Creating virtual environment (%s) in %s" % (prompt, basedir))
    venv.main(args)

def sandbox_venv(basedir: Path | str):
    ## simple usage case for the pylaborate_sandbox project
    env_prompt = os.getenv("VENV_PROMPT", PROMPT_DEFAULT)
    mk_venv(basedir, prompt = env_prompt, upgrade = True)

if __name__ == '__main__':
    ## run python in a subprocess, to create a virtual env
    rc = 1
    if len(sys.argv) > 1:
        ## env_dir will be provided to the subprocess callable
        env_dir = Path(sys.argv[1])
    else:
        env_dir = Path(__file__).parent.joinpath("env")
    try:
        ## spawning a new process, in lieu of calling venv as a shell script
        mp.set_start_method('spawn')
        p = mp.Process(target = sandbox_venv, args=(env_dir,))
        p.start()
        p.join()
        rc = 0
    except Exception as e:
        notify("Error: %s" % e)
    sys.exit(rc)
