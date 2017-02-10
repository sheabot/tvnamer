import os
import shutil

import utils

def same_partition(f1, f2):
    """Returns True if both files or directories are on the same partition
    """
    return os.stat(f1).st_dev == os.stat(f2).st_dev

def copy_file(old, new):
    #p("copy %s to %s" % (old, new))
    shutil.copyfile(old, new)
    shutil.copystat(old, new)

def rename_file(old, new):
    #p("rename %s to %s" % (old, new))
    stat = os.stat(old)
    os.rename(old, new)
    try:
        os.utime(new, (stat.st_atime, stat.st_mtime))
    except OSError as ex:
        if ex.errno == errno.EPERM:
            '''
            warn("WARNING: Could not preserve times for %s "
                 "(owner UID mismatch?)" % new)
            '''
        else:
            raise

def symlink_file(target, name):
    #p("symlink %s to %s" % (name, target))
    os.symlink(target, name)

def delete_file(fpath):
    """On OS X: Trashes a path using the Finder, via OS X's Scripting Bridge.

    On other platforms: unlinks file.
    """

    try:
        from AppKit import NSURL
        from ScriptingBridge import SBApplication
    except ImportError:
        #log().debug("Deleting %r" % fpath)
        os.unlink(fpath)
    else:
        #log().debug("Trashing %r" % fpath)
        targetfile = NSURL.fileURLWithPath_(fpath)
        finder = SBApplication.applicationWithBundleIdentifier_("com.apple.Finder")
        items = finder.items().objectAtLocation_(targetfile)
        items.delete()


class Renamer(object):
    """Deals with renaming of files
    """

    def __init__(self, config, filename):
        self.config = config
        self.utils = utils.Utils(config)
        self.filename = os.path.abspath(filename)

    def newPath(self, new_path = None, new_fullpath = None, force = False, always_copy = False, always_move = False, leave_symlink = False, create_dirs = True, getPathPreview = False):
        """Moves the file to a new path.

        If it is on the same partition, it will be moved (unless always_copy is True)
        If it is on a different partition, it will be copied, and the original
        only deleted if always_move is True.
        If the target file already exists, it will raise OSError unless force is True.
        If it was moved, a symlink will be left behind with the original name
        pointing to the file's new destination if leave_symlink is True.
        """

        if always_copy and always_move:
            raise ValueError("Both always_copy and always_move cannot be specified")

        if (new_path is None and new_fullpath is None) or (new_path is not None and new_fullpath is not None):
            raise ValueError("Specify only new_dir or new_fullpath")

        old_dir, old_filename = os.path.split(self.filename)
        if new_path is not None:
            # Join new filepath to old one (to handle realtive dirs)
            new_dir = os.path.abspath(os.path.join(old_dir, new_path))

            # Join new filename onto new filepath
            new_fullpath = os.path.join(new_dir, old_filename)

        else:
            # Join new filepath to old one (to handle realtive dirs)
            new_fullpath = os.path.abspath(os.path.join(old_dir, new_fullpath))

            new_dir = os.path.dirname(new_fullpath)


        if len(self.config['move_files_fullpath_replacements']) > 0:
            self.utils.p("Before custom full path replacements: %s" % (new_fullpath))
            new_fullpath = self.utils.applyCustomFullpathReplacements(new_fullpath)
            new_dir = os.path.dirname(new_fullpath)

        self.utils.p("New path: %s" % new_fullpath)

        if getPathPreview:
            return new_fullpath

        if create_dirs:
            try:
                os.makedirs(new_dir)
            except OSError as e:
                if e.errno != 17:
                    raise
            else:
                self.utils.p("Created directory %s" % new_dir)


        if os.path.isfile(new_fullpath):
            # If the destination exists, raise exception unless force is True
            if not force:
                raise OSError("File %s already exists, not forcefully moving %s" % (
                    new_fullpath, self.filename))

        if same_partition(self.filename, new_dir):
            if always_copy:
                # Same partition, but forced to copy
                copy_file(self.filename, new_fullpath)
            else:
                # Same partition, just rename the file to move it
                rename_file(self.filename, new_fullpath)

                # Leave a symlink behind if configured to do so
                if leave_symlink:
                    symlink_file(new_fullpath, self.filename)
        else:
            # File is on different partition (different disc), copy it
            copy_file(self.filename, new_fullpath)
            if always_move:
                # Forced to move file, we just trash old file
                self.utils.p("Deleting %s" % (self.filename))
                delete_file(self.filename)

                # Leave a symlink behind if configured to do so
                if leave_symlink:
                    symlink_file(new_fullpath, self.filename)

        self.filename = new_fullpath
