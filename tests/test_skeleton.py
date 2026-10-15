try:
    import pytest
except ImportError:  # original PyScaffold test is pytest-style; under plain unittest without pytest, skip instead of erroring
    import unittest
    raise unittest.SkipTest("tests/test_skeleton.py needs pytest (pip install pytest pytest-cov)")

from dentexmodel.skeleton import fib, main

__author__ = "awerdich"
__copyright__ = "awerdich"
__license__ = "MIT"


def test_fib():
    """API Tests"""
    assert fib(1) == 1
    assert fib(2) == 1
    assert fib(7) == 13
    with pytest.raises(AssertionError):
        fib(-10)


def test_main(capsys):
    """CLI Tests"""
    # capsys is a pytest fixture that allows asserts against stdout/stderr
    # https://docs.pytest.org/en/stable/capture.html
    main(["7"])
    captured = capsys.readouterr()
    assert "The 7-th Fibonacci number is 13" in captured.out
