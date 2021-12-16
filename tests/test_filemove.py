#!/usr/bin/env python3
import sys, os, pytest

# Adding parent dir to path to find and load module/file 'forecast_parser' in parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from filemover import *


# Dummy-test which will always succeed - must be replaced by real tests
def test_dummy():
    assert = True
