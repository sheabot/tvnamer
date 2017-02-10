import os

try:
    import json
except ImportError:
    import simplejson as json

from tvdb_api import Tvdb

import config_defaults
import utils
from compat import PY2
from episode_info import DatedEpisodeInfo, NoSeasonEpisodeInfo
from file_finder import FileFinder
from file_parser import FileParser
from renamer import Renamer
from tvnamer_exceptions import *

class TVNamer(object):

    def __init__(self, configFile=None, configData=None):
        self._loadConfig(configFile, configData)
        self._validateConfig()
        
        self.utils = utils.Utils(self.config)

    def _loadConfig(self, configFile=None, configData=None):
        # Check arguments
        if configFile is not None and configData is not None:
            raise RuntimeError("Cannot use configFile and configData arguments together")
        
        # Start with default config
        self.config = dict(config_defaults.defaults)
        if configFile:
            # Update default config from config file
            loadedConfig = json.load(open(os.path.expanduser(configFile)))
            self.config.update(loadedConfig)
        else:
            # Update default config from config data
            self.updateConfig(configData)

    def _validateConfig(self):
        # Batch mode
        if self.config["batch"]:
            self.config["select_first"] = True
            self.config["always_rename"] = True

        if self.config["move_files_only"] and not self.config["move_files_enable"]:
            raise ConfigValueError("Parameter 'move_files_enable' cannot be set to 'false' while parameter 'move_only' is set to 'true'.")

    def updateConfig(self, configData):
        if configData is not None:
            # Update config from config data
            self.config.update(configData)
            
    def getMoveDestination(self, episode):
        """Constructs the location to move/copy the file
        """

        #TODO: Write functional test to ensure this valid'ifying works
        def wrap_validfname(fname):
            """Wrap the makeValidFilename function as it's called twice
            and this is slightly long..
            """
            if self.config['move_files_lowercase_destination']:
                fname = fname.lower()
            return self.utils.makeValidFilename(
                fname,
                normalize_unicode = self.config['normalize_unicode_filenames'],
                windows_safe = self.config['windows_safe_filenames'],
                custom_blacklist = self.config['custom_filename_character_blacklist'],
                replace_with = self.config['replace_invalid_characters_with'])


        # Calls makeValidFilename on series name, as it must valid for a filename
        if isinstance(episode, DatedEpisodeInfo):
            destdir = self.config['move_files_destination_date'] % {
                'seriesname': self.utils.makeValidFilename(episode.seriesname),
                'year': episode.episodenumbers[0].year,
                'month': episode.episodenumbers[0].month,
                'day': episode.episodenumbers[0].day,
                'originalfilename': episode.originalfilename,
                }
        elif isinstance(episode, NoSeasonEpisodeInfo):
            destdir = self.config['move_files_destination'] % {
                'seriesname': wrap_validfname(episode.seriesname),
                'episodenumbers': wrap_validfname(self.utils.formatEpisodeNumbers(episode.episodenumbers)),
                'originalfilename': episode.originalfilename,
                }
        else:
            destdir = self.config['move_files_destination'] % {
                'seriesname': wrap_validfname(episode.seriesname),
                'seasonnumber': episode.seasonnumber,
                'episodenumbers': wrap_validfname(self.utils.formatEpisodeNumbers(episode.episodenumbers)),
                'originalfilename': episode.originalfilename,
                }
        return destdir


    def doRenameFile(self, cnamer, newName):
        """Renames the file. cnamer should be Renamer instance,
        newName should be string containing new filename.
        """
        try:
            cnamer.newPath(new_fullpath = newName, force = self.config['overwrite_destination_on_rename'], leave_symlink = self.config['leave_symlink'])
        except OSError as e:
            self.utils.warn(e)


    def doMoveFile(self, cnamer, destDir = None, destFilepath = None, getPathPreview = False):
        """Moves file to destDir, or to destFilepath
        """

        if (destDir is None and destFilepath is None) or (destDir is not None and destFilepath is not None):
            raise ValueError("Specify only destDir or destFilepath")

        if not self.config['move_files_enable']:
            raise ValueError("move_files feature is disabled but doMoveFile was called")

        if self.config['move_files_destination'] is None:
            raise ValueError("Config value for move_files_destination cannot be None if move_files_enabled is True")

        try:
            return cnamer.newPath(
                new_path = destDir,
                new_fullpath = destFilepath,
                always_move = self.config['always_move'],
                leave_symlink = self.config['leave_symlink'],
                getPathPreview = getPathPreview,
                force = self.config['overwrite_destination_on_move'])

        except OSError as e:
            self.utils.warn(e)


    def confirm(question, options, default = "y"):
        """Takes a question (string), list of options and a default value (used
        when user simply hits enter).
        Asks until valid option is entered.
        """
        # Highlight default option with [ ]
        options_str = []
        for x in options:
            if x == default:
                x = "[%s]" % x
            if x != '':
                options_str.append(x)
        options_str = "/".join(options_str)

        while True:
            self.utils.p(question)
            self.utils.p("(%s) " % (options_str), end="")
            try:
                ans = raw_input().strip()
            except KeyboardInterrupt as errormsg:
                self.utils.p("\n", errormsg)
                raise UserAbort(errormsg)

            if ans in options:
                return ans
            elif ans == '':
                return default

    def processFile(self, tvdb_instance, episode):
        """Gets episode name, prompts user for input
        """
        self.utils.p("# Processing file: %s" % episode.fullfilename)

        if len(self.config['input_filename_replacements']) > 0:
            replaced = self.utils.applyCustomInputReplacements(episode.fullfilename)
            self.utils.p("# With custom replacements: %s" % (replaced))

        # Use force_name option. Done after input_filename_replacements so
        # it can be used to skip the replacements easily
        if self.config['force_name'] is not None:
            episode.seriesname = self.config['force_name']

        self.utils.p("# Detected series: %s (%s)" % (episode.seriesname, episode.number_string()))

        try:
            episode.populateFromTvdb(tvdb_instance, force_name=self.config['force_name'], series_id=self.config['series_id'])
        except (DataRetrievalError, ShowNotFound) as errormsg:
            if self.config['always_rename'] and self.config['skip_file_on_error'] is True:
                self.utils.warn("Skipping file due to error: %s" % errormsg)
                return
            else:
                self.utils.warn(errormsg)
        except (SeasonNotFound, EpisodeNotFound, EpisodeNameNotFound) as errormsg:
            # Show was found, so use corrected series name
            if self.config['always_rename'] and self.config['skip_file_on_error']:
                self.utils.warn("Skipping file due to error: %s" % errormsg)
                return

            self.utils.warn(errormsg)

        cnamer = Renamer(self.config, episode.fullpath)


        shouldRename = False

        if self.config["move_files_only"]:

            newName = episode.fullfilename
            shouldRename = True

        else:
            newName = episode.generateFilename()
            if newName == episode.fullfilename:
                self.utils.p("#" * 20)
                self.utils.p("Existing filename is correct: %s" % episode.fullfilename)
                self.utils.p("#" * 20)

                shouldRename = True

            else:
                self.utils.p("#" * 20)
                self.utils.p("Old filename: %s" % episode.fullfilename)

                if len(self.config['output_filename_replacements']) > 0:
                    # Show filename without replacements
                    self.utils.p("Before custom output replacements: %s" % (episode.generateFilename(preview_orig_filename = False)))

                self.utils.p("New filename: %s" % newName)

                if self.config['always_rename']:
                    self.doRenameFile(cnamer, newName)
                    if self.config['move_files_enable']:
                        if self.config['move_files_destination_is_filepath']:
                            self.doMoveFile(cnamer = cnamer, destFilepath = self.getMoveDestination(episode))
                        else:
                            self.doMoveFile(cnamer = cnamer, destDir = self.getMoveDestination(episode))
                    return

                ans = self.confirm("Rename?", options = ['y', 'n', 'a', 'q'], default = 'y')

                if ans == "a":
                    self.utils.p("Always renaming")
                    self.config['always_rename'] = True
                    shouldRename = True
                elif ans == "q":
                    self.utils.p("Quitting")
                    raise UserAbort("User exited with q")
                elif ans == "y":
                    self.utils.p("Renaming")
                    shouldRename = True
                elif ans == "n":
                    self.utils.p("Skipping")
                else:
                    self.utils.p("Invalid input, skipping")

                if shouldRename:
                    self.doRenameFile(cnamer, newName)

        if shouldRename and self.config['move_files_enable']:
            newPath = self.getMoveDestination(episode)
            if self.config['move_files_destination_is_filepath']:
                self.doMoveFile(cnamer = cnamer, destFilepath = newPath, getPathPreview = True)
            else:
                self.doMoveFile(cnamer = cnamer, destDir = newPath, getPathPreview = True)

            if not self.config['batch'] and self.config['move_files_confirmation']:
                ans = self.confirm("Move file?", options = ['y', 'n', 'q'], default = 'y')
            else:
                ans = 'y'

            if ans == 'y':
                self.utils.p("Moving file")
                self.doMoveFile(cnamer, newPath)
            elif ans == 'q':
                self.utils.p("Quitting")
                raise UserAbort("user exited with q")
            
    def findFiles(self, paths):
        """Takes an array of paths, returns all files found
        """
        valid_files = []

        for cfile in paths:
            cur = FileFinder(
                self.config,
                cfile,
                with_extension = self.config['valid_extensions'],
                filename_blacklist = self.config["filename_blacklist"],
                recursive = self.config['recursive'])

            try:
                valid_files.extend(cur.findFiles())
            except InvalidPath:
                self.utils.warn("Invalid path: %s" % cfile)

        if len(valid_files) == 0:
            raise NoValidFilesFoundError()

        # Remove duplicate files (all paths from FileFinder are absolute)
        valid_files = list(set(valid_files))

        return valid_files

    def process(self, paths):
        episodes_found = []

        for cfile in self.findFiles(paths):
            parser = FileParser(self.config, cfile)
            try:
                episode = parser.parse()
            except InvalidFilename as e:
                self.utils.warn("Invalid filename: %s" % e)
            else:
                if episode.seriesname is None and self.config['force_name'] is None and self.config['series_id'] is None:
                    self.utils.warn("Parsed filename did not contain series name (and --name or --series-id not specified), skipping: %s" % cfile)
                else:
                    episodes_found.append(episode)

        if len(episodes_found) == 0:
            raise NoValidFilesFoundError()

        self.utils.p("# Found %d episode" % len(episodes_found) + ("s" * (len(episodes_found) > 1)))

        # Sort episodes by series name, season and episode number
        episodes_found.sort(key = lambda x: x.sortable_info())

        # episode sort order
        if self.config['order'] == 'dvd':
            dvdorder = True
        else:
            dvdorder = False

        if not PY2 and os.getenv("TRAVIS", "false") == "true":
            # Disable caching on Travis-CI because in Python 3 it errors with:
            #
            # Can't pickle <class 'http.cookiejar.DefaultCookiePolicy'>: it's not the same object as http.cookiejar.DefaultCookiePolicy
            cache = False
        else:
            cache = True

        tvdb_instance = Tvdb(
            interactive = False,
            search_all_languages = False,
            language = self.config['language'],
            dvdorder = dvdorder,
            cache=cache,
        )

        for episode in episodes_found:
            self.processFile(tvdb_instance, episode)
            self.utils.p('')
