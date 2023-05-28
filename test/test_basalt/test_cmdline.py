import asyncio as aio
from contextlib import contextmanager
import shellous
import sys
import traceback

from pylaborate.basalt.__main__ import Cmdline


class SampleAsyncRunner(Cmdline):
    def __init__(self):
        super().__init__()
        self._cmd = ("false",)

    @property
    def cmd(self):
        return self._cmd

    @property
    def loop(self):
        return self._loop

    def configure_argparser(self, parser):
        ## FIXME add some actual args here, short of emulating sh(1)
        pass

    def parse_more_args(self, restargs, _):
        self._cmd = tuple(restargs)
        return ()

    @contextmanager
    def consume_args(self, args):
        ## for example : extending Cmdline.consume_args
        with super().consume_args(args) as initial_restargs:
            if "--" in initial_restargs:
                initial_restargs.remove("--")
            next_restargs = self.parse_more_args(
                initial_restargs, self.option_namespace
            )
            yield next_restargs

    async def run(self):
        return await shellous.sh(*self.cmd)

    def run_sync(self, loop = None):
        _loop = loop if loop else aio.get_event_loop_policy().get_event_loop()
        return _loop.run_until_complete(self.run())

    def main(self, args):
        with self.consume_args(args):
            ## wih the @contextmanager implementation of consume_args()
            ## it would not "work out" to call consume_args directly here,
            ## without calling it as a context manager
            ##
            ## also, the implementaiton would fail if not calling consume_args
            ## ... as a context manager ... before dispatching to any form of 'run'
            pass
        try:
            out = self.run_sync()
            print(out)
            return 0
        except Exception as e:
            print("Error running %s: %s" % (self._cmd, str(e),), file=sys.stderr)
            tbk = e.__traceback__
            if tbk:
                traceback.print_tb(tbk, file=sys.stderr)
            return 1

