## pavement.py prototype [basalt project]

from asyncio.events import get_event_loop
from paver.easy import cmdopts, environment, options, task
import paver.tasks as tasks
from shellous import sh
import shlex
import sys
# from types import CoroutineType

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum

## not published, as yet, in the changeset repository
# from pylaborate.basalt.tasklib import write_conf


class DefaultVersions(StrEnum):
    pyqt5_version = "5.15.9",
    pyqt6_version = "6.5.0",
    pyside6_version = "6.5.0"


options(
    pyqt5_version = DefaultVersions.pyqt5_version,
    pyqt6_version = DefaultVersions.pyqt6_version,
    pyqt6_webengine_version = DefaultVersions.pyqt6_version,
    pyside6_version = DefaultVersions.pyside6_version,
)


## uses an as-yet unpublished source file
# @task
# def test_conf_json_write():
#     environment.options.conf_file = "/tmp/frob.json"
#     write_conf(environment)


##
# utility functions
##

async def qt6_path_dirs(options):
    qmake = shlex.split(options.qmake6)
    bindir = await(sh(*qmake, '-query', "QT_INSTALL_BINS"))
    libexecdir = await(sh(*qmake, '-query', "QT_INSTALL_LIBEXECS"))
    return (bindir.strip(), libexecdir.strip(),)

@cmdopts([("ping=", "i", "option test")])
def frob_a(options):
    print(f"Frob A @ {options!r}")


@cmdopts([("pong=", "o", "option test")])
def frob_b(options):
    print(f"Frob B @ {options!r}")


##
# task functions
##

@cmdopts([("pyqt6_sourcedir=", None, "PyQt6 source dir")])
def ensure_source_pyqt6(environment):
    print("ensure_source_pyqt6")
    ## FIXME trivial loop access, prototyping
    loop = None
    if hasattr(environment, 'event_loop'):
        loop = environment.event_loop
    else:
        loop = get_event_loop()
        environment.loop = loop
    ## FIXME running a function on the loop, from within a function
    ## called under a task -> running a function on a loop/executor
    ## managed within the Basalt Cmdline instance
    dirs = loop.run_until_complete(qt6_path_dirs(options))
    print(dirs)


##
# prototypes for async task definition / async task call
##

# Usage cases for async task handling:
# - subshell commands - shellous provides an async API
# - tasks running on network, e.g fetch-src
# - io-bound tasks, e.g checksum comparison
# - process-bound tasks, e.g building Qt components
#   and dist packages for projects using Qt in Python

@task
async def atask():
    '''coroutine-as-async-task test'''
    print("in atask")
    rslt = await sh("uname", "-a")
    if isinstance(rslt, str):
        print("uname: " + rslt.strip())
    else:
        print("subshell returned an unexpected value: %r" % rslt)

## first test: ensure that the 'atask' coroutine  is accessible from paver
#
# - the function that produces the coroutine is accessible under the
#   task.func attr
# - this function then runs the async task as a coroutine under an arbitrary
#   event loop
# - in this trivial instance, the async task's coroutine function requires
#   no args...
# - loop usage needs test under ipython/ipyparallel, ipython in spyder,
#   and jupyter notebooks
@task
def show_atask(environment):
    '''monitor/launcher for coroutine-as-async-task test'''
    atask_task = tasks.environment.get_task('atask')  # or fail ... (TBD)
    task_fun = atask_task.func
    print("atask: %r => %r  (%r)" % (atask_task, task_fun, atask_task.__class__))
    loop = get_event_loop()
    ## this [async] task does not require any args ....
    return loop.run_until_complete(task_fun())

## second test:
# - Implement an internal task loop (asyncio) in pylaborate.basalt.Basalt
# - call async task functions under an async await
# - call non-async task functions within a future-oriented result/exception wrapper
# - ensure that this will work out like a normal paver task:
#   $ python3 -m pylaborate.basalt atask
