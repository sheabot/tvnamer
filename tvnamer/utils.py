import os
import platform
import re

import unicode_helper
from compat import string_type
from tvnamer_exceptions import *

class Utils(object):

    def __init__(self, config):
        self.config = config
        
    def p(*args, **kw):
        unicode_helper.p(*args, **kw)

    def warn(self, text):
        """Displays message to sys.stderr
        """
        if self.config['verbose']:
            self.p(text, file = sys.stderr)

    def split_extension(self, filename):
        base = re.sub(self.config["extension_pattern"], "", filename)
        ext = filename.replace(base, "")
        return base, ext

    def _applyReplacements(self, cfile, replacements):
        """Applies custom replacements.

        Argument cfile is string.

        Argument replacements is a list of dicts, with keys "match",
        "replacement", and (optional) "is_regex"
        """
        for rep in replacements:
            if not rep.get('with_extension', False):
                # By default, preserve extension
                cfile, cext = self.split_extension(cfile)
            else:
                cfile = cfile
                cext = ""

            if 'is_regex' in rep and rep['is_regex']:
                cfile = re.sub(rep['match'], rep['replacement'], cfile)
            else:
                cfile = cfile.replace(rep['match'], rep['replacement'])

            # Rejoin extension (cext might be empty-string)
            cfile = cfile + cext

        return cfile

    def applyCustomInputReplacements(self, cfile):
        """Applies custom input filename replacements, wraps _applyReplacements
        """
        return self._applyReplacements(cfile, self.config['input_filename_replacements'])


    def applyCustomOutputReplacements(self, cfile):
        """Applies custom output filename replacements, wraps _applyReplacements
        """
        return self._applyReplacements(cfile, self.config['output_filename_replacements'])


    def applyCustomFullpathReplacements(self, cfile):
        """Applies custom replacements to full path, wraps _applyReplacements
        """
        return self._applyReplacements(cfile, self.config['move_files_fullpath_replacements'])

    def cleanRegexedSeriesName(self, seriesname):
        """Cleans up series name by removing any . and _
        characters, along with any trailing hyphens.

        Is basically equivalent to replacing all _ and . with a
        space, but handles decimal numbers in string, for example:

        >>> cleanRegexedSeriesName("an.example.1.0.test")
        'an example 1.0 test'
        >>> cleanRegexedSeriesName("an_example_1.0_test")
        'an example 1.0 test'
        """
        # TODO: Could this be made to clean "Hawaii.Five-0.2010" into "Hawaii Five-0 2010"?
        seriesname = re.sub("(\D)[.](\D)", "\\1 \\2", seriesname)
        seriesname = re.sub("(\D)[.]", "\\1 ", seriesname)
        seriesname = re.sub("[.](\D)", " \\1", seriesname)
        seriesname = seriesname.replace("_", " ")
        seriesname = re.sub("-$", "", seriesname)
        return seriesname.strip()

    def replaceInputSeriesName(self, seriesname):
        """allow specified replacements of series names

        in cases where default filenames match the wrong series,
        e.g. missing year gives wrong answer, or vice versa

        This helps the TVDB query get the right match.
        """
        for pat, replacement in self.config['input_series_replacements'].items():
            if re.match(pat, seriesname, re.IGNORECASE|re.UNICODE):
                return replacement
        return seriesname

    def replaceInputSeriesName(self, seriesname):
        """allow specified replacements of series names

        in cases where default filenames match the wrong series,
        e.g. missing year gives wrong answer, or vice versa

        This helps the TVDB query get the right match.
        """
        for pat, replacement in self.config['input_series_replacements'].items():
            if re.match(pat, seriesname, re.IGNORECASE|re.UNICODE):
                return replacement
        return seriesname


    def replaceOutputSeriesName(self, seriesname):
        """transform TVDB series names

        after matching from TVDB, transform the series name for desired abbreviation, etc.

        This affects the output filename.
        """

        return self.config['output_series_replacements'].get(seriesname, seriesname)

    def handleYear(self, year):
        """Handle two-digit years with heuristic-ish guessing

        Assumes 50-99 becomes 1950-1999, and 0-49 becomes 2000-2049

        ..might need to rewrite this function in 2050, but that seems like
        a reasonable limitation
        """

        year = int(year)

        # No need to guess with 4-digit years
        if year > 999:
            return year

        if year < 50:
            return 2000 + year
        else:
            return 1900 + year
            
    def formatEpisodeNumbers(self, episodenumbers):
        """Format episode number(s) into string, using configured values
        """
        if len(episodenumbers) == 1:
            epno = self.config['episode_single'] % episodenumbers[0]
        else:
            epno = self.config['episode_separator'].join(
                self.config['episode_single'] % x for x in episodenumbers)

        return epno
        
    def formatEpisodeName(self, names, join_with, multiep_format):
        """
        Takes a list of episode names, formats them into a string.

        If two names are supplied, such as "Pilot (1)" and "Pilot (2)", the
        returned string will be "Pilot (1-2)". Note that the first number
        is not required, for example passing "Pilot" and "Pilot (2)" will
        also result in returning "Pilot (1-2)".

        If two different episode names are found, such as "The first", and
        "Something else" it will return "The first, Something else"
        """
        if len(names) == 1:
            return names[0]

        found_name = ""
        numbers = []
        for cname in names:
            match = re.match("(.*) \(([0-9]+)\)$", cname)
            if found_name != "" and (not match or epname != found_name):
                # An episode didn't match
                return join_with.join(names)

            if match:
                epname, epno = match.group(1), match.group(2)
            else: # assume that this is the first episode, without number
                epname = cname
                epno = 1
            found_name = epname
            numbers.append(int(epno))

        return multiep_format % {'epname': found_name, 'episodemin': min(numbers), 'episodemax': max(numbers)}

    def makeValidFilename(self, value, normalize_unicode = False, windows_safe = False, custom_blacklist = None, replace_with = "_"):
        """
        Takes a string and makes it into a valid filename.

        normalize_unicode replaces accented characters with ASCII equivalent, and
        removes characters that cannot be converted sensibly to ASCII.

        windows_safe forces Windows-safe filenames, regardless of current platform

        custom_blacklist specifies additional characters that will removed. This
        will not touch the extension separator:

            >>> makeValidFilename("T.est.avi", custom_blacklist=".")
            'T_est.avi'
        """

        if windows_safe:
            # Allow user to make Windows-safe filenames, if they so choose
            sysname = "Windows"
        else:
            sysname = platform.system()

        # If the filename starts with a . prepend it with an underscore, so it
        # doesn't become hidden.

        # This is done before calling splitext to handle filename of ".", as
        # splitext acts differently in python 2.5 and 2.6 - 2.5 returns ('', '.')
        # and 2.6 returns ('.', ''), so rather than special case '.', this
        # special-cases all files starting with "." equally (since dotfiles have
        # no extension)
        if value.startswith("."):
            value = "_" + value

        # Treat extension seperatly
        value, extension = self.split_extension(value)

        # Remove any null bytes
        value = value.replace("\0", "")

        # Blacklist of characters
        if sysname == 'Darwin':
            # : is technically allowed, but Finder will treat it as / and will
            # generally cause weird behaviour, so treat it as invalid.
            blacklist = r"/:"
        elif sysname in ['Linux', 'FreeBSD']:
            blacklist = r"/"
        else:
            # platform.system docs say it could also return "Windows" or "Java".
            # Failsafe and use Windows sanitisation for Java, as it could be any
            # operating system.
            blacklist = r"\/:*?\"<>|"

        # Append custom blacklisted characters
        if custom_blacklist is not None:
            blacklist += custom_blacklist

        # Replace every blacklisted character with a underscore
        value = re.sub("[%s]" % re.escape(blacklist), replace_with, value)

        # Remove any trailing whitespace
        value = value.strip()

        # There are a bunch of filenames that are not allowed on Windows.
        # As with character blacklist, treat non Darwin/Linux platforms as Windows
        if sysname not in ['Darwin', 'Linux']:
            invalid_filenames = ["CON", "PRN", "AUX", "NUL", "COM1", "COM2",
            "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1",
            "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"]
            if value in invalid_filenames:
                value = "_" + value

        # Replace accented characters with ASCII equivalent
        if normalize_unicode:
            import unicodedata
            value = string_type(value) # cast data to unicode
            value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')

        # Truncate filenames to valid/sane length.
        # NTFS is limited to 255 characters, HFS+ and EXT3 don't seem to have
        # limits, FAT32 is 254. I doubt anyone will take issue with losing that
        # one possible character, and files over 254 are pointlessly unweidly
        max_len = 254

        if len(value + extension) > max_len:
            if len(extension) > len(value):
                # Truncate extension instead of filename, no extension should be
                # this long..
                new_length = max_len - len(value)
                extension = extension[:new_length]
            else:
                # File name is longer than extension, truncate filename.
                new_length = max_len - len(extension)
                value = value[:new_length]

        return value + extension

