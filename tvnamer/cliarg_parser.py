#!/usr/bin/env python

""" Constructs command line argument parser for tvnamer
"""

import argparse

def getCommandlineParser():
    parser = argparse.ArgumentParser(usage="%(prog)s [options] path [path2 ...]")

    # Console output
    g = parser.add_argument_group(title="Logging options", description="")
    g.add_argument("-v", "--verbose", action="store_true",  dest="verbose",  help="Show debugging info in console")
    g.add_argument("-q", "--quiet",   action="store_false", dest="verbose",  help="No verbose output (useful to override 'verbose':true in config file)")
    g.add_argument("--log-file",      action="store",       dest="log_file", help="Path to log file")

    # Config options
    g = parser.add_argument_group(title="Config options", description="")
    g.add_argument("-c", "--config",  action="store",       dest="loadconfig", help="Load config from this file")
    g.add_argument("-s", "--save",    action="store",       dest="saveconfig", help="Save configuration to this file and exit")
    g.add_argument("--dump-config",   action="store_true",  dest="showconfig", help="Show current config values and exit")

    # Batch options
    g = parser.add_argument_group(title="Override default/configured values", description="")
    g.add_argument("-b", "--batch",   action="store_true",  dest="batch",    help="Rename without human intervention")
    g.add_argument("--not-batch",     action="store_false", dest="batch",    help="Overrides --batch")
    g.add_argument("-r", "--recursive", action="store_true",  dest="recursive", help="Descend more than one level directories supplied as arguments")
    g.add_argument("--not-recursive",   action="store_false", dest="recursive", help="Only descend one level into directories")

    # Override values
    g = parser.add_argument_group(title="Override values from filename parser", description="")
    g.add_argument("--series-name",   action="store",       help="override the parsed series name with this (applies to all files)")
    g.add_argument("--series-id",     action="store",       help="explicitly set the show id for TVdb to use (applies to all files)")

    # TODO: this should probably be set only in config file
    parser.add_argument("-d", "--movedestination", action="store", dest="move_files_destination", help="Destination to move files to. Variables: %%(seriesname)s %%(seasonnumber)d %%(episodenumbers)s")

    # Positional arguments - paths to files/directories
    parser.add_argument("path", action="store", nargs="+", help="paths to files/directories")

    return parser

def parseConfigFile(default):
    """ Partially parse argument list, return specified config file.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-c", "--config",  action="store", default=default)
    known, unknown = parser.parse_known_args()
    return known.config


if __name__ == '__main__':
    config = parseConfigFile(None)
    print(config)

    p = getCommandlineParser()
    p.set_defaults(**{'recursive': True})
    print(p.parse_args(["foo", "bar"]))
