#!/usr/bin/env python

""" Test ability to force the series name or series id
"""

from functional_runner import run_tvnamer, verify_out_data
from nose.plugins.attrib import attr


@attr("functional")
def test_series_id():
    """Test --series-id argument
    """

    conf = """
    {"batch": true}
    """

    out_data = run_tvnamer(
        with_files = ['whatever.s01e01.avi'],
        with_config = conf,
        with_flags = ["--series-id", '76156'],
        with_input = "")

    expected_files = ['Scrubs - [01x01] - My First Day.avi']

    verify_out_data(out_data, expected_files)


@attr("functional")
def test_series_id_with_nameless_series():
    """Test --series-id argument with '6x17.etc.avi' type filename
    """

    conf = """
    {"always_rename": true,
    "select_first": true}
    """

    out_data = run_tvnamer(
        with_files = ['s01e01.avi'],
        with_config = conf,
        with_flags = ["--series-id", '76156', "--batch"],
        with_input = "")

    expected_files = ['Scrubs - [01x01] - My First Day.avi']

    verify_out_data(out_data, expected_files)


@attr("functional")
def test_temp_override():
    """Test --series-name argument
    """

    conf = """
    {"batch": true}
    """

    out_data = run_tvnamer(
        with_files = ['scrubs.s01e01.avi'],
        with_config = conf,
        with_flags = ["--series-name", "lost"],
        with_input = "")

    expected_files = ['Lost - [01x01] - Pilot (1).avi']

    verify_out_data(out_data, expected_files)
