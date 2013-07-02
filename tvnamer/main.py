#!/usr/bin/env python

""" Main tvnamer utility functionality
"""

import os
import sys
import logging

try:
    import json
except ImportError:
    import simplejson as json

from __init__ import __version__
from tvdb_api import Tvdb

import cliarg_parser
from config import Config

from utils import FileFinder, FileParser, applyCustomInputReplacements

from tvnamer_exceptions import (ConfigValueError, ShowNotFound, SeasonNotFound, EpisodeNotFound,
                                EpisodeNameNotFound, UserAbort, InvalidPath, NoValidFilesFoundError,
                                InvalidFilename, DataRetrievalError)

from renamer import Renamer


def log():
    """ Returns the logger for current file
    """
    return logging.getLogger(__name__)


def confirm(question, options, default="y"):
    """ Takes a question (string), list of options and a default value (used
        when user simply hits enter).
        Asks until valid option is entered.
    """

    # Highlight default option with [ ]
    options_str = [x if x != default else "[%s]" % x for x in options]
    options_str = "/".join(options_str)
    prompt = "%s (%s) " % (question, options_str)

    while True:
        try:
            ans = input(prompt).strip()
        except KeyboardInterrupt as errormsg:
            print("\n", errormsg)
            raise UserAbort(errormsg)

        if ans in options:
            return ans
        elif ans == '':
            return default


def processFile(tvdb_instance, episode):
    """ Gets episode name, prompts user for input
    """

    print("Processing file: '%s'" % episode.fullfilename)

    if len(Config['input_filename_replacements']) > 0:
        print("After input replacements: '%s'" % applyCustomInputReplacements(episode.fullfilename))

    print("Detected series: %s (%s)" % (episode.seriesname, episode.number_string()))
    print("")

    try:
        episode.populateFromTvdb(tvdb_instance, series_name=Config['series_name'], series_id=Config['series_id'])
    except (DataRetrievalError, ShowNotFound, SeasonNotFound, EpisodeNotFound, EpisodeNameNotFound) as errormsg:
        log().warn(errormsg)
        if Config['batch'] and Config['exit_on_error']:
            sys.exit(1)
        if Config['batch'] and Config['skip_file_on_error']:
            log().warn("Skipping file due to previous error.")
            return

    newFullPath = episode.getNewFullPath()
    print("")

    print("Old directory: '%s'" % os.path.dirname(episode.fullpath))
    print("New directory: '%s'" % os.path.dirname(newFullPath))
    print("")
    print("Old filename:  '%s'" % episode.fullfilename)
    print("New filename:  '%s'" % os.path.split(newFullPath)[1])
    print("")

    # don't do anything if filename was not changed
    if newFullPath == episode.fullpath:
        print("Existing filename is correct: '%s'" % episode.fullpath)
        return

    if not Config['batch'] and Config['move_files_confirmation']:
        ans = confirm("Move file?", options=['y', 'n', 'a', 'q'], default='y')
        if ans == "a":
            print("Always moving files")
            Config['move_files_confirmation'] = False
        elif ans == "q":
            print("Quitting")
            raise UserAbort("User exited with q")
        elif ans == "y":
            print("Renaming")
        elif ans == "n":
            print("Skipping")
            return
        else:
            print("Invalid input, skipping")
            return

    # finally move file
    cnamer = Renamer(episode.fullpath)
    try:
        cnamer.rename(
            new_fullpath=newFullPath,
            always_move=Config['always_move'],
            always_copy=Config['always_copy'],
            leave_symlink=Config['leave_symlink'],
            force=Config['overwrite_destination'])
    except OSError as e:
        log().warn(e)


def findFiles(paths):
    """ Takes an array of paths, returns all files found
    """

    valid_files = []
    finder = FileFinder(
        with_extension=Config['valid_extensions'],
        filename_blacklist=Config['filename_blacklist'],
        recursive=Config['recursive'])

    for cfile in paths:
        try:
            valid_files.extend(finder.findFiles(cfile))
        except InvalidPath:
            log().warn("Invalid path: '%s'" % cfile)

    if len(valid_files) == 0:
        raise NoValidFilesFoundError()

    # Remove duplicate files (all paths from FileFinder are absolute)
    valid_files = list(set(valid_files))

    return valid_files


def tvnamer(paths):
    """ Main tvnamer function, takes an array of paths, does stuff.
    """

    episodes_found = []

    for cfile in findFiles(paths):
        parser = FileParser(cfile)
        try:
            episode = parser.parse()
        except InvalidFilename as e:
            log().warn("Invalid filename: %s" % e)
        else:
            if episode.seriesname or Config['series_name'] or Config['series_id']:
                episodes_found.append(episode)
            else:
                log().warn("Parsed filename did not contain series name (and --series-name or --series-id not specified), skipping: %s" % cfile)

    if len(episodes_found) == 0:
        raise NoValidFilesFoundError()

    print("Found episodes: %d" % len(episodes_found))

    # Sort episodes by series name, season and episode number
    episodes_found.sort(key=lambda x: x.sortable_info())

    tvdb_instance = Tvdb(
        interactive=not Config['batch'],
        search_all_languages=Config['search_all_languages'],
        language=Config['language'])

    for episode in episodes_found:
        print("")
        print("#" * 20)
        processFile(tvdb_instance, episode)
        print("#" * 20)


class Logger:
    """ Helper class holding logging handlers, formatters etc. so that
        they can be added or removed at runtime.
    """

    def __init__(self):
        self.consoleFormatter = logging.Formatter('%(levelname)s - %(message)s')
        self.fileFormatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        self.rootLogger = logging.getLogger()
        self.rootLogger.setLevel(logging.DEBUG)
        self.consoleHandler = None
        self.fileHandler = None

    def initLogging(self, verbose_console=False, filename=""):
        """ Init logging to console and file specified by 'filename' argument.
            Maximum log level of console can be configured by 'consoleLogLevel' argument,
            log level of file is always DEBUG.
        """

        self.rootLogger.removeHandler(self.consoleHandler)
        self.rootLogger.removeHandler(self.fileHandler)

        # create console handler with INFO log level
        self.consoleHandler = logging.StreamHandler()
        if verbose_console:
            self.consoleHandler.setLevel(logging.DEBUG)
        else:
            self.consoleHandler.setLevel(logging.INFO)
        self.consoleHandler.setFormatter(self.consoleFormatter)
        self.rootLogger.addHandler(self.consoleHandler)

        # FIXME: this way messages recorded before initLogging(filename=foo.log) was called are lost
        #        find some way to hold messages until filename is specified?
        if filename:
            # create file handler with DEBUG log level
            self.fileHandler = logging.FileHandler(filename)
            self.fileHandler.setLevel(logging.DEBUG)
            self.fileHandler.setFormatter(self.fileFormatter)
            self.rootLogger.addHandler(self.fileHandler)

    def __del__(self):
        log().debug("tvnamer exited")
        logging.shutdown()


def main(default_config=None):
    """ Parses command line arguments, displays errors from tvnamer in terminal
    """

    logger = Logger()
    logger.initLogging()

    # initialize argument list parser
    parser = cliarg_parser.getCommandlineParser()

    # first parse only for config file
    config_path = cliarg_parser.parseConfigFile(default=default_config)

    # load the config
    if config_path is not None:
        log().info("Loading config file '%s'" % config_path)
        try:
            loadedConfig = json.load(open(os.path.expanduser(config_path)))
            config_version = loadedConfig.get("__version__") or "0"
            if __version__ > config_version:
                msg = "Old config file detected, please see "
                msg += "https://github.com/dbr/tvnamer/blob/master/tvnamer/config_defaults.py"
                msg += " and/or "
                msg += "https://github.com/dbr/tvnamer/blob/master/Changelog"
                msg += " and merge updates.\nProgram version: %s\nConfig version: %s" % (__version__, config_version)
                raise ConfigValueError(msg)
        except IOError:
            log().warn("Config file '%s' does not exist, using defaults" % config_path)
        except ValueError as e:
            log().error("Error loading config: %s" % e)
            parser.exit(1)
        except ConfigValueError as e:
            log().error("Error in config: %s" % e.message)
            parser.exit(1)
        else:
            # Update global config object
            Config.update(loadedConfig)

    # TODO: write function to check all exclusive options
    try:
        if Config['always_copy'] and Config['always_move']:
            raise ConfigValueError("Both always_copy and always_move cannot be specified.")
        if Config['titlecase_dynamic_parts'] and Config['lowercase_dynamic_parts']:
            raise ConfigValueError("Both 'lowercase_filename' and 'titlecase_filename' cannot be specified.")
    except ConfigValueError as e:
        log().error("Error in config: " + e.message)
        parser.exit(1)

    # set defaults, parse full argument list and update global config object
    parser.set_defaults(**Config)
    args = parser.parse_args()
    Config.update(args.__dict__)

    # re-init logging into file
    logger.initLogging(verbose_console=args.verbose, filename=args.log_file)
    log().debug("tvnamer started")

    # dump config into file or stdout
    if args.saveconfig or args.showconfig:
        configToSave = dict(args.__dict__)
        del configToSave['saveconfig']
        del configToSave['loadconfig']
        del configToSave['showconfig']

        # Save config argument
        if args.saveconfig:
            print("Saving config: %s" % (args.saveconfig))
            json.dump(
                configToSave,
                open(os.path.expanduser(args.saveconfig), "w+"),
                sort_keys=True,
                indent=4)

        # Show config argument
        elif args.showconfig:
            print(json.dumps(configToSave, sort_keys=True, indent=4))

        return

    try:
        args.path.sort()
        tvnamer(paths=args.path)
    except NoValidFilesFoundError:
        parser.error("No valid files were supplied")
    except UserAbort as errormsg:
        parser.exit(errormsg)

if __name__ == '__main__':
    # Decode args using filesystem encoding
    # Needed for unicode support (test_unicode.py)
    # FIXME: better solution?
    if sys.version_info[0] < 3:
        sys.argv = [x.decode(sys.getfilesystemencoding()) for x in sys.argv]

    # don't load default config in tests!!!
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        del sys.argv[1]
        main()
    else:
        main(default_config=os.path.expanduser("~/.tvnamer.json"))
