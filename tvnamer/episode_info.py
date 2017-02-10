import os

import utils
from tvdb_api import (tvdb_error, tvdb_shownotfound, tvdb_seasonnotfound,
    tvdb_episodenotfound, tvdb_attributenotfound, tvdb_userabort)
from tvnamer_exceptions import *


class EpisodeInfo(object):
    """Stores information (season, episode number, episode name), and contains
    logic to generate new name
    """

    CFG_KEY_WITH_EP = "filename_with_episode"
    CFG_KEY_WITHOUT_EP = "filename_without_episode"

    def __init__(self,
        config,
        seriesname,
        seasonnumber,
        episodenumbers,
        episodename = None,
        filename = None,
        extra = None):

        self.config = config
        self.utils = utils.Utils(config)
        self.seriesname = seriesname
        self.seasonnumber = seasonnumber
        self.episodenumbers = episodenumbers
        self.episodename = episodename
        self.fullpath = filename
        if filename is not None:
            # Remains untouched, for use when renaming file
            self.originalfilename = os.path.basename(filename)
        else:
            self.originalfilename = None

        if extra is None:
            extra = {}
        self.extra = extra

    def fullpath_get(self):
        return self._fullpath

    def fullpath_set(self, value):
        self._fullpath = value
        if value is None:
            self.filename, self.extension = None, None
        else:
            self.filepath, self.filename = os.path.split(value)
            self.filename, self.extension = self.utils.split_extension(self.filename)

    fullpath = property(fullpath_get, fullpath_set)

    @property
    def fullfilename(self):
        return u"%s%s" % (self.filename, self.extension)

    def sortable_info(self):
        """Returns a tuple of sortable information
        """
        return (self.seriesname, self.seasonnumber, self.episodenumbers)

    def number_string(self):
        """Used in UI
        """
        return "season: %s, episode: %s" % (
            self.seasonnumber,
            ", ".join([str(x) for x in self.episodenumbers]))

    def populateFromTvdb(self, tvdb_instance, force_name=None, series_id=None):
        """Queries the tvdb_api.Tvdb instance for episode name and corrected
        series name.
        If series cannot be found, it will warn the user. If the episode is not
        found, it will use the corrected show name and not set an episode name.
        If the site is unreachable, it will warn the user. If the user aborts
        it will catch tvdb_api's user abort error and raise tvnamer's
        """
        try:
            if series_id is None:
                show = tvdb_instance[force_name or self.seriesname]
            else:
                series_id = int(series_id)
                tvdb_instance._getShowData(series_id, self.config['language'])
                show = tvdb_instance[series_id]
        except tvdb_error as errormsg:
            raise DataRetrievalError("Error with www.thetvdb.com: %s" % errormsg)
        except tvdb_shownotfound:
            # No such series found.
            raise ShowNotFound("Show %s not found on www.thetvdb.com" % self.seriesname)
        except tvdb_userabort as error:
            raise UserAbort(string_type(error))
        else:
            # Series was found, use corrected series name
            self.seriesname = self.utils.replaceOutputSeriesName(show['seriesname'])

        if isinstance(self, DatedEpisodeInfo):
            # Date-based episode
            epnames = []
            for cepno in self.episodenumbers:
                try:
                    sr = show.airedOn(cepno)
                    if len(sr) > 1:
                        raise EpisodeNotFound(
                            "Ambigious air date %s, there were %s episodes on that day" % (
                            cepno, len(sr)))
                    epnames.append(sr[0]['episodename'])
                except tvdb_episodenotfound:
                    raise EpisodeNotFound(
                        "Episode that aired on %s could not be found" % (
                        cepno))
            self.episodename = epnames
            return

        if not hasattr(self, "seasonnumber") or self.seasonnumber is None:
            # Series without concept of seasons have all episodes in season 1
            seasonnumber = 1
        else:
            seasonnumber = self.seasonnumber

        epnames = []
        for cepno in self.episodenumbers:
            try:
                episodeinfo = show[seasonnumber][cepno]

            except tvdb_seasonnotfound:
                raise SeasonNotFound(
                    "Season %s of show %s could not be found" % (
                    seasonnumber,
                    self.seriesname))

            except tvdb_episodenotfound:
                # Try to search by absolute_number
                sr = show.search(cepno, "absolute_number")
                if len(sr) > 1:
                    # For multiple results try and make sure there is a direct match
                    unsure = True
                    for e in sr:
                        if int(e['absolute_number']) == cepno:
                            epnames.append(e['episodename'])
                            unsure = False
                    # If unsure error out
                    if unsure:
                        raise EpisodeNotFound(
                            "No episode actually matches %s, found %s results instead" % (cepno, len(sr)))
                elif len(sr) == 1:
                    epnames.append(sr[0]['episodename'])
                else:
                    raise EpisodeNotFound(
                        "Episode %s of show %s, season %s could not be found (also tried searching by absolute episode number)" % (
                            cepno,
                            self.seriesname,
                            seasonnumber))

            except tvdb_attributenotfound:
                raise EpisodeNameNotFound(
                    "Could not find episode name for %s" % cepno)
            else:
                epnames.append(episodeinfo['episodename'])

        self.episodename = epnames

    def getepdata(self):
        """
        Uses the following config options:
        filename_with_episode # Filename when episode name is found
        filename_without_episode # Filename when no episode can be found
        episode_single # formatting for a single episode number
        episode_separator # used to join multiple episode numbers
        """
        # Format episode number into string, or a list
        epno = self.utils.formatEpisodeNumbers(self.episodenumbers)

        # Data made available to config'd output file format
        if self.extension is None:
            prep_extension = ''
        else:
            prep_extension = self.extension

        epdata = {
            'seriesname': self.seriesname,
            'seasonno': self.seasonnumber, # TODO: deprecated attribute, make this warn somehow
            'seasonnumber': self.seasonnumber,
            'episode': epno,
            'episodename': self.episodename,
            'ext': prep_extension}

        return epdata

    def generateFilename(self, lowercase = False, preview_orig_filename = False):
        epdata = self.getepdata()

        # Add in extra dict keys, without clobbering existing values in epdata
        extra = self.extra.copy()
        extra.update(epdata)
        epdata = extra

        if self.episodename is None:
            fname = self.config[self.CFG_KEY_WITHOUT_EP] % epdata
        else:
            if isinstance(self.episodename, list):
                epdata['episodename'] = self.utils.formatEpisodeName(
                    self.episodename,
                    join_with = self.config['multiep_join_name_with'],
                    multiep_format = self.config['multiep_format'])
            fname = self.config[self.CFG_KEY_WITH_EP] % epdata

        if self.config['titlecase_filename']:
            from _titlecase import titlecase
            fname = titlecase(fname)

        if lowercase or self.config['lowercase_filename']:
            fname = fname.lower()

        if preview_orig_filename:
            # Return filename without custom replacements or filesystem-validness
            return fname

        if len(self.config['output_filename_replacements']) > 0:
            fname = self.utils.applyCustomOutputReplacements(fname)

        return self.utils.makeValidFilename(
            fname,
            normalize_unicode = self.config['normalize_unicode_filenames'],
            windows_safe = self.config['windows_safe_filenames'],
            custom_blacklist = self.config['custom_filename_character_blacklist'],
            replace_with = self.config['replace_invalid_characters_with'])

    def __repr__(self):
        return u"<%s: %r>" % (
            self.__class__.__name__,
            self.generateFilename())
            
            
class DatedEpisodeInfo(EpisodeInfo):
    CFG_KEY_WITH_EP = "filename_with_date_and_episode"
    CFG_KEY_WITHOUT_EP = "filename_with_date_without_episode"

    def __init__(self,
        config,
        seriesname,
        episodenumbers,
        episodename = None,
        filename = None,
        extra = None):

        self.config = config
        self.utils = utils.Utils(config)
        self.seriesname = seriesname
        self.episodenumbers = episodenumbers
        self.episodename = episodename
        self.fullpath = filename

        if filename is not None:
            # Remains untouched, for use when renaming file
            self.originalfilename = os.path.basename(filename)
        else:
            self.originalfilename = None

        if filename is not None:
            # Remains untouched, for use when renaming file
            self.originalfilename = os.path.basename(filename)
        else:
            self.originalfilename = None

        if extra is None:
            extra = {}
        self.extra = extra

    def sortable_info(self):
        """Returns a tuple of sortable information
        """
        return (self.seriesname, self.episodenumbers)

    def number_string(self):
        """Used in UI
        """
        return "episode: %s" % (
            ", ".join([str(x) for x in self.episodenumbers]))

    def getepdata(self):
        # Format episode number into string, or a list
        dates = str(self.episodenumbers[0])
        if isinstance(self.episodename, list):
            prep_episodename = self.utils.formatEpisodeName(
                self.episodename,
                join_with = self.config['multiep_join_name_with'],
                multiep_format = self.config['multiep_format'])
        else:
            prep_episodename = self.episodename

        # Data made available to config'd output file format
        if self.extension is None:
            prep_extension = ''
        else:
            prep_extension = self.extension

        epdata = {
            'seriesname': self.seriesname,
            'episode': dates,
            'episodename': prep_episodename,
            'ext': prep_extension}

        return epdata
        
        
class NoSeasonEpisodeInfo(EpisodeInfo):
    CFG_KEY_WITH_EP = "filename_with_episode_no_season"
    CFG_KEY_WITHOUT_EP = "filename_without_episode_no_season"

    def __init__(self,
        config,
        seriesname,
        episodenumbers,
        episodename = None,
        filename = None,
        extra = None):

        self.config = config
        self.utils = utils.Utils(config)
        self.seriesname = seriesname
        self.episodenumbers = episodenumbers
        self.episodename = episodename
        self.fullpath = filename

        if filename is not None:
            # Remains untouched, for use when renaming file
            self.originalfilename = os.path.basename(filename)
        else:
            self.originalfilename = None

        if extra is None:
            extra = {}
        self.extra = extra

    def sortable_info(self):
        """Returns a tuple of sortable information
        """
        return (self.seriesname, self.episodenumbers)

    def number_string(self):
        """Used in UI
        """
        return "episode: %s" % (
            ", ".join([str(x) for x in self.episodenumbers]))

    def getepdata(self):
        epno = self.utils.formatEpisodeNumbers(self.episodenumbers)

        # Data made available to config'd output file format
        if self.extension is None:
            prep_extension = ''
        else:
            prep_extension = self.extension

        epdata = {
            'seriesname': self.seriesname,
            'episode': epno,
            'episodename': self.episodename,
            'ext': prep_extension}

        return epdata


class AnimeEpisodeInfo(NoSeasonEpisodeInfo):
    CFG_KEY_WITH_EP = "filename_anime_with_episode"
    CFG_KEY_WITHOUT_EP = "filename_anime_without_episode"

    CFG_KEY_WITH_EP_NO_CRC = "filename_anime_with_episode_without_crc"
    CFG_KEY_WITHOUT_EP_NO_CRC = "filename_anime_without_episode_without_crc"

    def generateFilename(self, lowercase = False, preview_orig_filename = False):
        epdata = self.getepdata()

        # Add in extra dict keys, without clobbering existing values in epdata
        extra = self.extra.copy()
        extra.update(epdata)
        epdata = extra

        # Get appropriate config key, depending on if episode name was
        # found, and if crc value was found
        if self.episodename is None:
            if self.extra.get('crc') is None:
                cfgkey = self.CFG_KEY_WITHOUT_EP_NO_CRC
            else:
                # Have crc, but no ep name
                cfgkey = self.CFG_KEY_WITHOUT_EP
        else:
            if self.extra.get('crc') is None:
                cfgkey = self.CFG_KEY_WITH_EP_NO_CRC
            else:
                cfgkey = self.CFG_KEY_WITH_EP

        if self.episodename is not None:
            if isinstance(self.episodename, list):
                epdata['episodename'] = self.utils.formatEpisodeName(
                    self.episodename,
                    join_with = self.config['multiep_join_name_with'],
                    multiep_format = self.config['multiep_format'])

        fname = self.config[cfgkey] % epdata


        if lowercase or self.config['lowercase_filename']:
            fname = fname.lower()

        if preview_orig_filename:
            # Return filename without custom replacements or filesystem-validness
            return fname

        if len(self.config['output_filename_replacements']) > 0:
            fname = self.utils.applyCustomOutputReplacements(fname)

        return self.utils.makeValidFilename(
            fname,
            normalize_unicode = self.config['normalize_unicode_filenames'],
            windows_safe = self.config['windows_safe_filenames'],
            custom_blacklist = self.config['custom_filename_character_blacklist'],
            replace_with = self.config['replace_invalid_characters_with'])
            