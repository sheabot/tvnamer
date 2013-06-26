#!/usr/bin/env python

"""Tests anime filename output
"""

from functional_runner import run_tvnamer, verify_out_data
from nose.plugins.attrib import attr


@attr("functional")
def test_group():
    """Anime filename [#100]
    """
    out_data = run_tvnamer(
        with_files = ['[Some Group] Scrubs - 01 [A1B2C3].avi'],
        with_config = """
{
    "batch": true,

    "filename_anime_with_episode": "[%(group)s] %(seriesname)s - %(episode)s - %(episodename)s [%(crc)s]%(ext)s"
}
""")

    expected_files = ['[Some Group] Scrubs - 01 - My First Day [A1B2C3].avi']

    verify_out_data(out_data, expected_files)


@attr("functional")
def test_group_no_epname():
    """Anime filename, on episode with no name [#100]
    """
    out_data = run_tvnamer(
        with_files = ['[Some Group] Somefakeseries - 01 [A1B2C3].avi'],
        with_config = """
{
    "batch": true,

    "filename_anime_without_episode": "[%(group)s] %(seriesname)s - %(episode)s [%(crc)s]%(ext)s"
}
""")

    expected_files = ['[Some Group] Somefakeseries - 01 [A1B2C3].avi']

    verify_out_data(out_data, expected_files)


@attr("functional")
def test_ambiguity_fix():
    """Test amiguous eisode number fix
    """

    conf = """
    {"batch": true}
    """

    out_data = run_tvnamer(
        with_files = ['[ANBU-AonE]_Naruto_43_[3811CBB5].avi'],
        with_config = conf,
        with_flags = [],
        with_input = "")

    expected_files = ['[ANBU-AonE] Naruto - 43 - Killer Kunoichi and a Shaky Shikamaru [3811CBB5].avi']

    verify_out_data(out_data, expected_files)
