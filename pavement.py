## pavement.py prototype [basalt project]

from asyncio.events import get_event_loop
from paver.easy import cmdopts, environment, options, task
from dataclasses import dataclass
import paver.tasks as tasks
from shellous import sh
import shlex


# from types import CoroutineType


## not published, as yet, in the changeset repository
# from pylaborate.basalt.tasklib import write_conf


@dataclass(init = False, eq = False, order = False, frozen=True)
class DefaultVersions():
    ## approximation of a StrEnum class,
    ## without portability issues (temporary definition)
    pyqt5_version = "5.15.9",
    pyqt6_version = "6.5.0",
    pyside6_version = "6.5.0"


options(
    ## default options for build test => Python/Qt build
    qmake6="qmake6",
    qmake5="qmake-qt5",
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

def run_async_task(name, *args, **kwargs):
    ## for purpose of ctrl-group testing under paver w/o extensions in basalt
    ## and for testing extensions in basalt
    atask_task = tasks.environment.get_task(name)
    if not atask_task:
        raise RuntimeError(f"run_async_task: Task not found: {name!r}")
    task_fun = atask_task.func
    print("async task %s: %r => %r (%r)" % (name, atask_task, task_fun, atask_task.__class__))
    policy = aio.get_event_loop_policy()
    loop = None
    try:
        ## this may fail under some thread configurations
        loop = policy.get_event_loop()
    except RuntimeError:
        loop = policy.new_event_loop()
    coro = task_fun(*args, **kwargs)
    if loop.is_running():
        print("!! async task %r: call @ soon" % name)
        loop.call_soon(coro)
    else:
        print("!! async task %r: call @ run" % name)
        loop.run_until_complete(coro)

async def qt6_path_dirs(sh, options, qmake = options.qmake6 ):
    _qmake = None
    if isinstance(qmake, str):
        _qmake = shlex.split(qmake)
    else:
        _qmake = qmake

    bindir = await(sh(*_qmake, '-query', "QT_INSTALL_BINS"))
    libexecdir = await(sh(*_qmake, '-query', "QT_INSTALL_LIBEXECS"))
    return (bindir.strip(), libexecdir.strip(),)

@cmdopts(
    [("options=", "o", "comma-separated list of options to display (default: all)")]
)
def show_options(options):
    ## implemented primarily in pyalborate.basalt.__main__
    ##
    ## example call:
    ## $ paver show_options -o show_options
    ##
    ## FIXME 'options' not being configured under task exec in basalt,
    ## though ostensibly set with a corresponding paver Bunch named
    ## for each arg-receiving task, under environment.options (also in basalt)
    ##
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

@task
def show_environment():
    ## implemented primarily in pyalborate.basalt.__main__
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
                ## TBD ...
                # autopep8: off
 # fmt: off
                print("%s ? (Exception when accessing value: %r)" % (name, exc,))
                # autopep8: on
                # fmt: on


@task
def default():
    '''default task [testing]'''
    print(">> In Task: Default task [nop]")


@task
@cmdopts([("qmake6=", "m", "qmake6 path")])  ## FIXME add to args for all tasks (extension)
async def show_path_dirs(options, qmake6=options.qmake6):
    '''async task test with option definitions'''
    if hasattr(options, 'show_path_dirs'):
        print(f'!!! DxBG task args qmake6: {getattr(getattr(options, "show_path_dirs"),"qmake6", "NONE!")}')
    if not qmake6:
        raise RuntimeError("options configuration failed in show_path_dirs, no qmake6 argv")
    for d in await qt6_path_dirs(options, qmake6):
        print("=> Path dir: " + d)

@task
def show_path_dirs_sync(options):
    '''call the "show_path_dirs" task synchronously'''
    run_async_task('show_path_dirs', options)


@task
def auto():
    '''auto task [testing]'''
    print(">> In Task: Auto task [nop]")

@cmdopts([("ping=", "i", "option test")])
def opt_test_a(options):
    '''options test A'''
    print(f">> Options Test A @ {options.opt_test_a!r}")


@cmdopts([("pong=", "o", "option test")])
@needs("opt_test_a")
def opt_test_b(options):
    '''options test B'''
    print(f">> Options Test B @ {options.opt_test_b!r}")

@consume_args
def consumer(args):
    '''consume_args test'''
    print(f">> consumer args: {args!r}")


@consume_nargs(3)
def n_consumer(args):
    '''consume_nargs test'''
    print(f">> n_consumer args: {args!r}")




##
# task functions
##

@cmdopts([("pyqt6_sourcedir=", None, "PyQt6 source dir")])
def ensure_source_pyqt6(environment):
    '''prototype task for a build system'''
    print("ensure_source_pyqt6")
    ## FIXME trivial loop access, prototyping
    loop = None
    if hasattr(environment, 'event_loop'):
        loop = environment.event_loop
    else:
        loop = aio.get_event_loop()
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
async def shfalse(sh):
    '''shell parser test (false)'''
    tbd = await sh("false")
    print("shfalse => %s" % repr(tbd))

    try:
        async with sh("false") as falserunner:
            ## the Shellous Runner object is directly accessible here
            ##
            ## after exit from this context, if the falserunner was
            ## stored in the calling environment, the object could
            ## be tested for its return code
            print("shfalse runner => %s" % repr(falserunner))
    except shellous.result.ResultError:
        pass

    return True

@task
async def shparse(sh):
    '''shell parser test (each async line)'''

    ## example: retrieve a process-like object with shellous,
    ## with stream initialization for output capture via basalt
    ## sh task args onto a local StringIO buffer
    ##
    ## - The process itself will be run under a PTY here
    ##
    ## - When initializing a shellous Runner under `async with`,
    ##   this will prevent any exception signaling if the process
    ##   exits with a non-zero return code
    ##
    ## - This assumes that a `tty` command is available in the
    ##   shell path

    import io
    out = io.StringIO()
    async with sh("tty", stdout = out, stdin = sh.Redirect.DEFAULT, pty = True) as obj:
        print("=> " + repr(obj))
    print("> " + out.getvalue())

import io
import os
import re

@task
async def sudotest(sh):
    '''tentative test for using sudo with shellous'''
    askpass = os.environ.get('SUDO_ASKPASS', os.environ.get("SSH_ASKPASS",  "/usr/local/bin/ksshaskpass"))
    if askpass:
        os.environ["SUDO_ASKPASS"] = askpass

    out = io.StringIO()
    err = io.StringIO()
    shrunner = None
    async with sh(shlex.split("sudo pwd"), stderr = err, stdout = out, stdin = None, pty = True, inherit_env = True, close_fds=True) as runner:
        ## Implementation Note:
        ## - sudo may try to read from stdin unless pty=True, close_fds=True
        ##
        print(" => " + repr(runner))
        shrunner = runner

    if shrunner.returncode != 0:
        print("! non-zero exit from sudo subcmd")
        return -1

    print(">> " + out.getvalue().rstrip())
    if len(err.getvalue()) is not int(0):
        err.seek(0)
        for line in err.readlines():
            print("!> " + line.rstrip())

@task
async def asleep():
    '''async utility for testing signal handling and task scheduling'''
    await aio.sleep(float('inf'))

@task
async def shsleep(sh, future):
    '''shell utility for testing process cancellation'''
    runner = None
    async with sh("sleep", str(2**16), future = future) as shrunner:
        ## one exhaustive approach towards ensuring that the process
        ## will not run indefinitely ...
        future.add_done_callback(lambda fut: shrunner.cancel() if fut.cancelled() else False)
        runner = shrunner
    print(f"returning from shsleep @ {runner!r} ({runner.cancelled})")



@task
async def atask(sh):
    '''coroutine-as-async-task test'''
    print("[[in atask]]")

    rslt = await sh("uname", "-a", stdout = True) ## TBD test pty=... arg
    if isinstance(rslt, str) and len(rslt) is not int(0):
        ## FIXME when redirecting to std{out, err} it still returns a string == ''
        print("uname: %r" % rslt)
        return rslt.strip()
    else:
        return rslt

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
def atask_sync(sh):
    '''call the "atask" task synchronously'''
    run_async_task('atask', sh)

@task
async def shfail_nocmd(sh):
    '''asynchronous task designed to fail in a shell command'''
    await sh('xpwd')

## second test:
# - Implement an internal task loop (asyncio) in pylaborate.basalt.Basalt
# - call async task functions under an async await
# - call non-async task functions within a future-oriented result/exception wrapper
# - ensure that this will work out like a normal paver task:
#   $ python3 -m pylaborate.basalt atask
