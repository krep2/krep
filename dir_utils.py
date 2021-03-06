
import os
import shutil


class AutoChangedDir(object):
    def __init__(self, newdir, cleanup=True):
        self.currdir = os.getcwd()
        self.newdir = newdir
        self.cleanup = cleanup
        self.created = False

    def __enter__(self):
        if not os.path.exists(self.newdir):
            os.makedirs(self.newdir)
            self.created = True

        if self.newdir != self.currdir:
            os.chdir(self.newdir)

    def __exit__(self, exc_type, exc_value, traceback):
        if self.newdir != self.currdir:
            os.chdir(self.currdir)
            if self.created and self.cleanup:
                shutil.rmtree(self.newdir)
