import os
import sys
import subprocess
import Queue
import threading

flac_files = []
mp3_files = []

flac_dir = 'flac'
mp3_dir = 'mp3'

file_queue = Queue.Queue()

def is_flac_file(file):
    return True

def read_dir(dir):
    files = os.listdir(dir)
    for f in files:
        t = os.path.join(dir, f)
        if os.path.isdir(t):
            read_dir(t)
        else:
            if is_flac_file(file):
                flac_files.append(t)

def read_flac_dir(flac_dir):
    cwd = os.getcwd()
    os.chdir(flac_dir)
    read_dir('.')
    os.chdir(cwd)

def prepare_files_list(flac_dir, mp3_dir):
    for f in flac_files:
        mp3f = os.path.splitext(f)[0] + ".mp3"
        mp3f = os.path.join(mp3_dir,mp3f)
        f = os.path.join(flac_dir, f)
        mp3_files.append((f, mp3f))

def prepare_transcode_queue(out_dir):
    for f in mp3_files:
        mp3f = f[1]
        dir = os.path.split(mp3f)[0]
        if not os.path.exists(dir):
            os.makedirs(dir)
        file_queue.put(f)

class ThreadTranscode(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

    def run(self):
        while not self.queue.empty():
            try:
                file_pair = self.queue.get_nowait()
                print "Transcoding file %s into %s" % file_pair
                flac = ['flac', '-d', '-c', file_pair[0]]
                lame = ['lame', '-V0', '-', file_pair[1]]
                p_flac = subprocess.Popen(flac, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                p_lame = subprocess.Popen(lame, stdin=p_flac.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                p_lame.wait()
                (o, e) = p_lame.communicate()
                self.queue.task_done()
            except:
                print "Nothing more in the work Queue"

read_flac_dir(flac_dir)
prepare_files_list(flac_dir, mp3_dir)
prepare_transcode_queue(mp3_dir)

print "Transcoding started"

for i in range(4):
    t = ThreadTranscode(file_queue)
    t.daemon = True
    t.start()

file_queue.join()

print "Transcoding complete"

