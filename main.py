from subprocess import Popen, PIPE
import time
import traceback
import os

from couchpotato.core.logger import CPLog
from couchpotato.core.event import addEvent, fireEvent
from couchpotato.core.plugins.base import Plugin
from couchpotato.environment import Env

log = CPLog(__name__)


class Stackit(Plugin):

    def __init__(self):

        # check if development setting is enabled to load new code and trigger renamer automatically
        if Env.get('dev'):
            def test():
                fireEvent('renamer.scan')
            addEvent('app.load', test)

        addEvent('renamer.after', self.stackit, priority=80)

    def stackit(self, message = None, group = None):
        if not group: group = {}

        # group['destination_dir'] ex: E:\Movies\Avatar.(2009)
        # group['identifier'] ex: tt0089218
        # group['filename'] ex: Avatar.(2009)
        # group['renamed_files'] ex: [u'E:\Movies\Avatar.(2009)\Avatar.(2009).DVD-Rip.cd1.avi', u'E:\Movies\Avatar.(2009)\Avatar.(2009).DVD-Rip.cd2.avi']
        log.debug("IMDB identifier: %s", group['identifier'])
        log.debug("Movie name: %s", group['dirname'])
        log.debug("Downloaded Movie directory: %s", group['parentdir'])
        log.debug("Renamed Movie Files: %s", group['renamed_files'])

        movie_path = group['destination_dir']
        log.info("Found movie on: %s", movie_path)
        movielist, cleanlist = self.getMovieFiles(movie_path)
        if not movielist:
            log.info("No unstacked movies found on: %s", movie_path)
        else:
            log.info("Found %s unstacked movie files for movie: %s", (str(len(movielist[movie_path])), movie_path))
            log.debug("Unstacked files: %s", movielist[movie_path])
            log.debug("Clean files: %s", cleanlist[movie_path])
            self.process(movielist, cleanlist, group)

    def getMovieFiles(self, movie_path):

        exts = []
        clean = []
        movielist = {}
        moviefiles = []
        cleanlist = {}
        cleanfiles = []

        for x in range(1, 10):
            # movie extensions
            exts.append(".cd{0}.avi".format(x))
            exts.append(".cd{0}.mkv".format(x))
            exts.append(".cd{0}.mp4".format(x))
            # cleaning extensions
            clean.append(".cd{0}.sub".format(x))
            clean.append(".cd{0}.idx".format(x))
            clean.append(".cd{0}.srt".format(x))
            clean.append(".cd{0}.nfo".format(x))

        log.info("Searching for unstacked movie on folder: %s", movie_path)
        for f in os.listdir(movie_path):
            if os.path.isfile(os.path.join(movie_path, f)):
                lowercase = f.lower()
                # find part files pattern on movie file
                if any(ext in lowercase for ext in exts):
                    fname = os.path.join(movie_path, f)
                    moviefiles.append(fname)
                    cleanfiles.append(fname)
                    log.debug("Added movie part file %s", fname)
                if any(c in lowercase for c in clean):
                    cname = os.path.join(movie_path, f)
                    cleanfiles.append(cname)
                    log.debug("Added file %s for post-processing cleaning routine", cname)

        if moviefiles:
            movielist[movie_path] = moviefiles
        if cleanfiles:
            cleanlist[movie_path] = cleanfiles

        return movielist, cleanlist

    def remove_file(self, filepath):

        try:
            os.remove(os.path.realpath(filepath))
            log.info("Permanently removed file %s!", filepath)
        except:
            log.error("There was a problem removing file: %s!", filepath)
            pass

    def cleanfiles(self, cleanlist, movietxt, group):

        for moviepath in cleanlist.keys():
            log.info("Cleaning leftover files for movie folder: %s", moviepath)
            log.debug("Leftovers: %s", cleanlist[moviepath])
            for leftover in cleanlist[moviepath]:
                log.debug("Deleting leftover: %s", leftover)
                # delete leftovers from movie folder
                try:
                    self.remove_file(leftover)
                    log.info("Successfully deleted leftover file %s from movie directory", os.path.realpath(leftover))
                except:
                    log.debug("There was a problem deleting leftover file %s from movie directory: %s", (leftover, (traceback.format_exc())))
                    pass
                # delete leftovers from renamed_files
                try:
                    group['renamed_files'].remove(os.path.realpath(leftover))
                    log.info("Successfully removed leftover file %s from group['renamed_files']", os.path.realpath(leftover))
                except:
                    log.debug("There was a problem removing leftover file %s from group['renamed_files']: %s", (leftover, (traceback.format_exc())))
                    pass
        # delete movietxt
        try:
            self.remove_file(movietxt)
            log.info("Successfully deleted movietxt file %s from movie directory", movietxt)
        except:
            log.debug("There was a problem deleting movietxt file %s from movie directory: %s", (movietxt, (traceback.format_exc())))
            pass

    def process(self, movies, cleanlist, group):

        for moviepath in movies.keys():
            movietxt = moviepath + '.txt'
            f = open(movietxt, 'w')
            for moviepart in movies[moviepath]:
                moviefile = moviepart.replace("'", r"'\''")
                f.write('file ' + "'" + moviefile + "'" + '\n')
            f.flush()
            f.close()
            extension = os.path.splitext(moviepart)[1].lower()
            movie_output = moviepart.rsplit('.', 2)[0] + extension

            try:
                log.info("Stacking movie: %s", moviepath)
                ffmpeg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin\\ffmpeg.exe")
                ffmpeg_command = [ffmpeg_path, "-f", "concat", "-i", movietxt, "-c", "copy", "-y", movie_output]
                log.info("Running FFMPEG with arguments: %s", ffmpeg_command)
                ffmpeg = Popen(ffmpeg_command, stdout=PIPE)
                res = ffmpeg.wait()
                if res == 0:
                    log.info("Stacking movie: %s finished successfully!", moviepath)
                    # update renamed_files list with final movie file
                    try:
                        group['renamed_files'].append(os.path.realpath(movie_output))
                        log.info("Added stacked movie file %s to group['renamed_files']", os.path.realpath(movie_output))
                    except:
                        log.debug("There was a problem adding stacked movie file %s to group['renamed_files']: %s", (movie_output, (traceback.format_exc())))
                        pass

                    # Cleaning routines
                    if cleanlist:
                        time.sleep(2)
                        log.info("Cleaning Up movie: %s by removing processed files!", moviepath)
                        self.cleanfiles(cleanlist, movietxt, group)
                        log.info("Successfully cleaned up movie: %s!", moviepath)

                    # Script ran as expected!
                    log.debug("Updated Renamed Movie Files: %s", group['renamed_files'])
                    return True
                else:
                    log.info("Stackit returned an error code: %s", str(res))
            except:
                log.error("Failed to stack movie(s): %s", (traceback.format_exc()))

            return False