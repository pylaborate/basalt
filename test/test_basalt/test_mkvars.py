from assertpy import assert_that
from datetime import datetime
import os
from pathlib import Path
from pylaborate.common_staging import first, last
from pytest import fixture, mark

from typing import Sequence, Generator

from pylaborate.basalt.mkvars import optional_files, get_venv_bindir
import pylaborate.basalt.mkvars as subject

def test_setvars():
    mkv = subject.MkVars()

    mkv.setvars(
        ## test data translated from a project Makefile (env.mk)

        build_dir="build",
        stampdir="{build_dir}/.build_stamp",
        host_python="python3",
        venv_dir="env",
        env_cfg="{venv_dir}/pyvenv.cfg",
        pyproject_cfg="pyproject.toml",
        # fmt: off
        requirements_in=optional_files("requirements.in"),
        requirements_local=optional_files("requirements.local"),
        # requirements_nop: test case - value source, generator => empty tuple
        requirements_nop=optional_files("/nonexistent/requirements.txt"),
        requirements_txt="requirements.txt",
        requirements_depends=lambda: (mkv.pyproject_cfg, *mkv.requirements_nop, *mkv.requirements_in, *mkv.requirements_local,),
        # fmt: on
        project_py="project.py",
        pyproject_extras=("dev",),
        homedir=os.path.expanduser("~"),
        pip_cache="{homedir}/.cache/pip",

        pip_options="--no-build-isolation -v --cache-dir={pip_cache!r}",
        # fmt: off
        opt_extras=lambda: " ".join("--extra {opt}".format(opt = opt) for opt in mkv.pyproject_extras),
        pip_compile_options='--cache-dir={pip_cache!r} --resolver=backtracking -v --pip-args {pip_options!r} {opt_extras}',
        # fmt: on
        pip_sync_options="-v --ask --pip-args {pip_options!r}",
        env_bindir=lambda: get_venv_bindir(mkv.venv_dir),
        env_pip="{env_bindir}/pip",
        env_pip_compile="{env_bindir}/pip-compile",
        pip_compile_depends=lambda: ("{env_pip_compile}", *mkv.requirements_depends),

        ## additional test data
        home_path=Path("~"),
        beta_dct=dict(a="{pip_cache}", b="{project_py}"),
        beta_int=51,
    )

    assert_that(mkv['stampdir']).is_equal_to("{build_dir}/.build_stamp".format(**mkv))

    # return mkv

