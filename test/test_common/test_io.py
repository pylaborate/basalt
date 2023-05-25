## tests for pylaborate.common_staging.io

from assertpy import assert_that
import re
import os


import pylaborate.common_staging.io as subject


def test_PolyIO():
    thisdir = os.path.dirname(__file__)
    test_text = None
    stream = None
    with subject.PolyIO(os.path.join(thisdir, "resource_io_00.txt")) as io:
        test_text = io.read()
        stream = io
    test_lines = re.split("[\n\r]+", test_text)
    assert_that(len(test_lines)).is_equal_to(3)
    assert_that(test_lines[0]).is_equal_to("test @ line one")
    assert_that(test_lines[1]).is_equal_to("test @ line two")
    assert_that(test_lines[2]).is_equal_to("EOF without line break")
    assert_that(stream.closed).is_true()
