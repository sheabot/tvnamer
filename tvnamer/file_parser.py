import datetime
import os
import re

import utils
from episode_info import *
from tvnamer_exceptions import *

class FileParser(object):
    """Deals with parsing of filenames
    """

    def __init__(self, config, path):
        self.config = config
        self.path = path
        self.utils = utils.Utils(config)
        self.compiled_regexs = []
        self._compileRegexs()

    def _compileRegexs(self):
        """Takes episode_patterns from config, compiles them all
        into self.compiled_regexs
        """
        for cpattern in self.config['filename_patterns']:
            try:
                cregex = re.compile(cpattern, re.VERBOSE)
            except re.error as errormsg:
                self.utils.warn("WARNING: Invalid episode_pattern (error: %s)\nPattern:\n%s" % (
                    errormsg, cpattern))
            else:
                self.compiled_regexs.append(cregex)

    def parse(self):
        """Runs path via configured regex, extracting data from groups.
        Returns an EpisodeInfo instance containing extracted data.
        """
        _, filename = os.path.split(self.path)

        filename = self.utils.applyCustomInputReplacements(filename)

        for cmatcher in self.compiled_regexs:
            match = cmatcher.match(filename)
            if match:
                namedgroups = match.groupdict().keys()

                if 'episodenumber1' in namedgroups:
                    # Multiple episodes, have episodenumber1 or 2 etc
                    epnos = []
                    for cur in namedgroups:
                        epnomatch = re.match('episodenumber(\d+)', cur)
                        if epnomatch:
                            epnos.append(int(match.group(cur)))
                    epnos.sort()
                    episodenumbers = epnos

                elif 'episodenumberstart' in namedgroups:
                    # Multiple episodes, regex specifies start and end number
                    start = int(match.group('episodenumberstart'))
                    end = int(match.group('episodenumberend'))
                    if end - start > 5:
                        self.utils.warn("WARNING: %s episodes detected in file: %s, confused by numeric episode name, using first match: %s" %(end - start, filename, start))
                        episodenumbers = [start]
                    elif start > end:
                        # Swap start and end
                        start, end = end, start
                        episodenumbers = list(range(start, end + 1))
                    else:
                        episodenumbers = list(range(start, end + 1))

                elif 'episodenumber' in namedgroups:
                    episodenumbers = [int(match.group('episodenumber')), ]

                elif 'year' in namedgroups or 'month' in namedgroups or 'day' in namedgroups:
                    if not all(['year' in namedgroups, 'month' in namedgroups, 'day' in namedgroups]):
                        raise ConfigValueError(
                            "Date-based regex must contain groups 'year', 'month' and 'day'")
                    match.group('year')

                    year = self.utils.handleYear(match.group('year'))

                    episodenumbers = [datetime.date(year,
                                                    int(match.group('month')),
                                                    int(match.group('day')))]

                else:
                    raise ConfigValueError(
                        "Regex does not contain episode number group, should"
                        "contain episodenumber, episodenumber1-9, or"
                        "episodenumberstart and episodenumberend\n\nPattern"
                        "was:\n" + cmatcher.pattern)

                if 'seriesname' in namedgroups:
                    seriesname = match.group('seriesname')
                else:
                    raise ConfigValueError(
                        "Regex must contain seriesname. Pattern was:\n" + cmatcher.pattern)

                if seriesname != None:
                    seriesname = self.utils.cleanRegexedSeriesName(seriesname)
                    seriesname = self.utils.replaceInputSeriesName(seriesname)

                extra_values = match.groupdict()

                if 'seasonnumber' in namedgroups:
                    seasonnumber = int(match.group('seasonnumber'))

                    episode = EpisodeInfo(
                        config = self.config,
                        seriesname = seriesname,
                        seasonnumber = seasonnumber,
                        episodenumbers = episodenumbers,
                        filename = self.path,
                        extra = extra_values)
                elif 'year' in namedgroups and 'month' in namedgroups and 'day' in namedgroups:
                    episode = DatedEpisodeInfo(
                        config = self.config,
                        seriesname = seriesname,
                        episodenumbers = episodenumbers,
                        filename = self.path,
                        extra = extra_values)
                elif 'group' in namedgroups:
                    episode = AnimeEpisodeInfo(
                        config = self.config,
                        seriesname = seriesname,
                        episodenumbers = episodenumbers,
                        filename = self.path,
                        extra = extra_values)
                else:
                    # No season number specified, usually for Anime
                    episode = NoSeasonEpisodeInfo(
                        config = self.config,
                        seriesname = seriesname,
                        episodenumbers = episodenumbers,
                        filename = self.path,
                        extra = extra_values)

                return episode
        else:
            emsg = "Cannot parse %r" % self.path
            if len(self.config['input_filename_replacements']) > 0:
                emsg += " with replacements: %r" % filename
            raise InvalidFilename(emsg)
