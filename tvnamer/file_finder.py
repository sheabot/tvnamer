import os
import re

import utils
from compat import string_type
from tvnamer_exceptions import *

class FileFinder(object):
    """Given a file, it will verify it exists. Given a folder it will descend
    one level into it and return a list of files, unless the recursive argument
    is True, in which case it finds all files contained within the path.

    The with_extension argument is a list of valid extensions, without leading
    spaces. If an empty list (or None) is supplied, no extension checking is
    performed.

    The filename_blacklist argument is a list of regexp strings to match against
    the filename (minus the extension). If a match is found, the file is skipped
    (e.g. for filtering out "sample" files). If [] or None is supplied, no
    filtering is done
    """

    def __init__(self, config, path, with_extension = None, filename_blacklist = None, recursive = False):
        self.config = config
        self.utils = utils.Utils(config)
        self.path = path
        if with_extension is None:
            self.with_extension = []
        else:
            self.with_extension = with_extension
        if filename_blacklist is None:
            self.with_blacklist = []
        else:
            self.with_blacklist = filename_blacklist
        self.recursive = recursive

    def findFiles(self):
        """Returns list of files found at path
        """
        if os.path.isfile(self.path):
            path = os.path.abspath(self.path)
            if self._checkExtension(path) and not self._blacklistedFilename(path):
                return [path]
            else:
                return []
        elif os.path.isdir(self.path):
            return self._findFilesInPath(self.path)
        else:
            raise InvalidPath("%s is not a valid file/directory" % self.path)

    def _checkExtension(self, fname):
        """Checks if the file extension is blacklisted in valid_extensions
        """
        if len(self.with_extension) == 0:
            return True

        # don't use split_extension here (otherwise valid_extensions is useless)!
        _, extension = os.path.splitext(fname)
        for cext in self.with_extension:
            cext = ".%s" % cext
            if extension == cext:
                return True
        else:
            return False

    def _blacklistedFilename(self, filepath):
        """Checks if the filename (optionally excluding extension)
        matches filename_blacklist

        self.with_blacklist should be a list of strings and/or dicts:

        a string, specifying an exact filename to ignore
        "filename_blacklist": [".DS_Store", "Thumbs.db"],

        a dictionary, where each dict contains:

        Key 'match' - (if the filename matches the pattern, the filename
        is blacklisted)

        Key 'is_regex' - if True, the pattern is treated as a
        regex. If False, simple substring check is used (if
        cur['match'] in filename). Default is False

        Key 'full_path' - if True, full path is checked. If False, only
        filename is checked. Default is False.

        Key 'exclude_extension' - if True, the extension is removed
        from the file before checking. Default is False.
        """

        if len(self.with_blacklist) == 0:
            return False

        fdir, fullname = os.path.split(filepath)
        fname, fext = self.utils.split_extension(fullname)

        for fblacklist in self.with_blacklist:
            if isinstance(fblacklist, string_type):
                if fullname == fblacklist:
                    return True
                else:
                    continue

            if "full_path" in fblacklist and fblacklist["full_path"]:
                to_check = filepath
            else:
                if fblacklist.get("exclude_extension", False):
                    to_check = fname
                else:
                    to_check = fullname

            if fblacklist.get("is_regex", False):
                m = re.match(fblacklist["match"], to_check)
                if m is not None:
                    return True
            else:
                m = fblacklist["match"] in to_check
                if m:
                    return True
        else:
            return False

    def _findFilesInPath(self, startpath):
        """Finds files from startpath, could be called recursively
        """
        allfiles = []
        if not os.access(startpath, os.R_OK):
            self.utils.p("Skipping inaccessible path %s" % startpath)
            return allfiles

        for subf in os.listdir(string_type(startpath)):
            newpath = os.path.join(startpath, subf)
            newpath = os.path.abspath(newpath)
            if os.path.isfile(newpath):
                if not self._checkExtension(subf):
                    continue
                elif self._blacklistedFilename(subf):
                    continue
                else:
                    allfiles.append(newpath)
            else:
                if self.recursive:
                    allfiles.extend(self._findFilesInPath(newpath))
                #end if recursive
            #end if isfile
        #end for sf
        return allfiles
