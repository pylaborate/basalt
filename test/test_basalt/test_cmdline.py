import argparse as ap
import asyncio as aio
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

    def consume_args(self, args):
        ## for example : extending Cmdline.consume_args
        initial_restargs = super().consume_args(args)
        if "--" in initial_restargs:
            initial_restargs.remove("--")
        return self.parse_more_args(
            initial_restargs, self.option_namespace
        )

    async def run(self):
        return await shellous.sh(*self.cmd)

    def run_sync(self, loop = None):
        _loop = loop if loop else aio.get_event_loop_policy().get_event_loop()
        return _loop.run_until_complete(self.run())

    def main(self, args):
        self.consume_args(args)
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

