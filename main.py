from subprocess import Popen, PIPE, STDOUT
import time
import traceback
import os
import errno
import collections

from couchpotato.core.log import CPLog
from couchpotato.core.event import addEvent, fireEvent
from couchpotato.core.helpers.variable import splitString
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

    def stackit(self, message=None, group=None):

        if (len(argv) == 0 or len(argv) >= 2):
            log.info("============================================================")
            log.info("== How to use stackit: stackit.py <movies_root_directory> ==")
            log.info("============================================================")
        
        movielist = getMovieFiles(argv)
        if not movielist:
            log.info("No movies on %s to process", os.path.normpath(argv[0]).upper())
        else:
            process(movielist)

    def getMovieFiles(argv):
    
        exts=[]
        filelist={}
        dirfiles=[]
        
        for x in range(1,10):
            exts.append(".CD{0}.avi".format(x))
            exts.append(".CD{0}.mkv".format(x))
            exts.append(".CD{0}.mp4".format(x))
        
        log.info("Searching for unstacked movies on library: %s...", os.path.normpath(argv[0]).upper())
        log.info("Searching files on root directory...")
        for f in os.listdir(argv[0]):
            if os.path.isfile(os.path.join(argv[0], f)):
                for ext in exts:
                    uppername = f.upper()
                    if uppername.find(ext.upper()) != -1:
                        fname = os.path.join(argv[0], f)
                        dirfiles.append(fname)
                        log.debug("Added movie part file %s ... !", fname)
                filelist[argv[0]] = dirfiles
        dirfiles = []

        for root, dirs, files in os.walk(argv[0]):
            for dir in dirs:    
                log.info("Searching movie files on %s sub-directory...", dir)
                for ext in exts:
                    for name in os.listdir(os.path.join(root, dir)):
                        uppername = name.upper()
                        if uppername.find(ext.upper()) != -1:
                            fname = os.path.join(root, dir, name)
                            dirfiles.append(fname)
                            filelist[os.path.join(root, dir)] = dirfiles
                dirfiles = []
        
        return collections.OrderedDict(sorted(filelist.items(), key = lambda t: t[0]))
     
    def remove_file(filepath):
    
        try:
            os.remove(os.path.realpath(filepath))
            log.info("Permanently removed file %s!", filepath)
        except:
            log.error("There was a problem removing file: %s!", filepath)
            pass
    
    def process(movies):
    
        movie_count = 0
        movie_error_count = 0
        startTime = time.time()
        
        for moviepath in movies.keys():
            movietxt = moviepath + '.txt'
            f = open(movietxt, 'w') 
            for moviepart in movies[moviepath]:
                moviefile = moviepart.replace("'", r"'\''")
                f.write('file ' + "'" + moviefile + "'" + '\n')
            f.flush() 
            f.close()            
            extension = os.path.splitext(moviepart)[1].lower()
            movie_output = moviepart.rsplit('.',2)[0] + extension
        
            try:
                log.info("Stacking movie: %s", moviepath)
                ffmpeg_command = ["bin\\ffmpeg.exe", "-f", "concat", "-i", movietxt, "-c", "copy", "-y", movie_output]
                log.info("Running FFMPEG with arguments: %s", ffmpeg_command)
                ffmpeg = Popen(ffmpeg_command, stdout=PIPE, stderr=STDOUT)
                output = ffmpeg.communicate()
                if ffmpeg.returncode == 0:  
                    log.info("Stacking movie: %s finished successfully!", moviepath)
                    time.sleep(2)
                    log.info("Cleaning Up movie: %s by removing part files and temporary input file: %s!", (moviepath, movietxt))
                    for moviepart in movies[moviepath]:
                        remove_file(moviepart)
                        time.sleep(0.5)		  
                    remove_file(movietxt)
                    log.info("Finished cleaning up movie: %s successfully!", moviepath)
                    movie_count += 1
                    return True	
                else:
                    log.debug(output + '\n')
                    log.error("Stacking movie: %s was unsuccessfully!", moviepath)
                    movie_error_count += 1
            except:
                log.error("Failed to stack movie(s): %s", (traceback.format_exc()))

            return False

        endTime = time.time()
        proc_time = str((round(endTime - startTime)))
        log.info("##############################################")
        log.info("				Runtime: %s seconds		         ", proc_time)
        log.info("##############################################")
        log.info(" [%i] Movie(s) were stacked successfully.     ", movie_count)
        log.info("##############################################")
        log.info(" [%i] Movie(s) generated processing errors!   ", movie_error_count)
        log.info("##############################################")
        
        