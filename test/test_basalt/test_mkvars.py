from assertpy import assert_that
import os
from pathlib import Path
from pytest import fixture, mark

from pylaborate.basalt.mkvars import optional_files, get_venv_bindir
import pylaborate.basalt.mkvars as subject


def test_setvars():
    mkv = subject.MkVars()

    mkv.define(
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
        mapped_dct=dict(a="{pip_cache}", b="{project_py}"),
        mapped_int=51,
    )

    print("! TEST mkvars values => " + repr(tuple(v for v in mkv.values())))
    print("! TEST mkvars items => " + repr(tuple((k, v,) for k, v in mkv.items())))

    mkdup = mkv.dup()

    ## test value expansion for sources after MkVars.define()
    assert_that(mkdup.stampdir).is_equal_to("{build_dir}/.build_stamp".format_map(mkv))
    assert_that(mkdup.value(mkdup.stampdir)).is_equal_to("{build_dir}/.build_stamp".format_map(mkv))
    assert_that(mkv.stampdir).is_equal_to("{build_dir}/.build_stamp".format_map(mkv))
    assert_that(mkv.value(mkv.stampdir)).is_equal_to("{build_dir}/.build_stamp".format_map(mkv))

    assert_that(mkv['stampdir']).is_equal_to("{build_dir}/.build_stamp".format_map(mkv))
    assert_that(mkdup['stampdir']).is_equal_to("{build_dir}/.build_stamp".format_map(mkv))

    ## test generator expansion

    assert_that(mkdup.requirements_depends).contains("requirements.in")
    assert_that(mkdup['requirements_depends']).contains("requirements.in")

    assert_that(mkv.requirements_depends).contains("requirements.in")
    assert_that(mkv['requirements_depends']).contains("requirements.in")

    ## test dict expansion
    assert_that(mkdup.mapped_dct.keys()).contains("a", "b")
    for value in mkdup.mapped_dct.values():
        assert_that(isinstance(value, str)).is_true()
        assert_that("{" in value).is_false()
    assert_that(mkdup.mapped_dct['a']).is_equal_to("{pip_cache}".format_map(mkdup))
    assert_that(mkdup.mapped_dct['b']).is_equal_to("{project_py}".format_map(mkdup))

    assert_that(mkv.mapped_dct.keys()).contains("a", "b")
    for value in mkv.mapped_dct.values():
        assert_that(isinstance(value, str)).is_true()
        assert_that("{" in value).is_false()
    assert_that(mkv.mapped_dct['a']).is_equal_to("{pip_cache}".format_map(mkv))
    assert_that(mkv.mapped_dct['b']).is_equal_to("{project_py}".format_map(mkv))

    ## re-test after reset()
    mkv.reset()
    mkdup.reset()

    assert_that(mkdup.value(mkdup.stampdir)).is_equal_to("{build_dir}/.build_stamp".format(**mkv))
    assert_that(mkv.value(mkv.stampdir)).is_equal_to("{build_dir}/.build_stamp".format(**mkv))
    assert_that(mkv['stampdir']).is_equal_to("{build_dir}/.build_stamp".format(**mkv))
    assert_that(mkdup['stampdir']).is_equal_to("{build_dir}/.build_stamp".format(**mkv))

    assert_that(mkdup.requirements_depends).contains("requirements.in")
    assert_that(mkdup['requirements_depends']).contains("requirements.in")
    assert_that(mkv.requirements_depends).contains("requirements.in")
    assert_that(mkv['requirements_depends']).contains("requirements.in")




