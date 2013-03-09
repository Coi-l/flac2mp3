import os
import sys
import subprocess
import Queue
import threading
import shutil

import mutagen
from mutagen.flac import FLAC
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.id3 import TIT2

flac_files = []
audio_file_pairs = []

misc_files = []
misc_file_pairs = []
 
flac_dir = 'flac'
mp3_dir = 'mp3'

transcode_queue = Queue.Queue()
copy_queue = Queue.Queue()
tag_queue = Queue.Queue()

def is_flac_file(file):
    return file.endswith(".flac")

def read_dir(dir):
    files = os.listdir(dir)
    for f in files:
        t = os.path.join(dir, f)
        if os.path.isdir(t):
            read_dir(t)
        else:
            if is_flac_file(t):
                flac_files.append(t)
            else:
                misc_files.append(t)

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
        audio_file_pairs.append((f, mp3f))

    for f in misc_files:
        newf = os.path.join(mp3_dir, f)
        orgf = os.path.join(flac_dir, f)
        misc_file_pairs.append((orgf, newf))

def prepare_file_queues():
    for f in audio_file_pairs:
        mp3f = f[1]
        dir = os.path.split(mp3f)[0]
        if not os.path.exists(dir):
            os.makedirs(dir)
        transcode_queue.put(f)

    for f in misc_file_pairs:
        copy_queue.put(f)

class ThreadTranscode(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

    def run(self):
        while not self.queue.empty():
            file_pair = None
            try:
                file_pair = self.queue.get_nowait()
            except Exception as e:
                print e
                print "Nothing more in the work Queue"

            if file_pair:
                try:
                    if not os.path.exists(file_pair[1]):
                        print "Transcoding file %s into %s" % file_pair
                        flac = ['flac', '-d', '-c', file_pair[0]]
                        lame = ['lame', '-V0', '-', file_pair[1]]
                        p_flac = subprocess.Popen(flac, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        p_lame = subprocess.Popen(lame, stdin=p_flac.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        p_lame.wait()
                        (o, e) = p_lame.communicate()
                    else:
                        print "%s already exists, not doing anything" % file_pair[1]
                except Exception as e:
                    print e

                self.queue.task_done()

#Thread to mirror tags from flac to mp3 files
class TagsMirror(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

    def run(self):
        while not self.queue.empty():
            try:
                file_pair = self.queue.get_nowait()
            except Exception as e:
                print e
                print "Nothing more in the work queue"

            if file_pair:
                try:
                    self.move_tags(file_pair)
                except Exception as e:
                    print e

            self.queue.task_done()

    def move_tags(self, file_pair):
        print "Moving tags from %s to %s" % file_pair
        self.write_default_tag(file_pair[1])
        flac = FLAC(file_pair[0])
        mp3 = EasyID3(file_pair[1])
        for key in flac:
            try:
                mp3[key] = flac[key]
            except Exception as e:
                pass
        mp3.save()

    def write_default_tag(self, mp3_file_name):
        mp3 = MP3(mp3_file_name)
        mp3["TIT2"] = TIT2(encoding=3, text=["Default"])
        mp3.save()

#Thread to mirror the non flac files
class ThreadMirror(threading.Thread):
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue

    def run(self):
        while not self.queue.empty():
            try:
                file_pair = self.queue.get_nowait()
            except Exception as e:
                print e
                print "Nothing more in the work queue"

            if file_pair:
                try:
                    if not os.path.exists(file_pair[1]):
                        print "Copying %s to %s" % file_pair
                        shutil.copyfile(file_pair[0], file_pair[1])
                    else:
                        print "%s already exists, not doing anything" % file_pair[1]
                except Exception as e:
                    print e

            self.queue.task_done()


read_flac_dir(flac_dir)
prepare_files_list(flac_dir, mp3_dir)
prepare_file_queues()


print "Transcoding started"

for i in range(4):
    t = ThreadTranscode(transcode_queue)
    t.daemon = True
    t.start()

transcode_queue.join()
print "Transcoding complete"

print "Moving tags from flac to mp3 files"

for f in audio_file_pairs:
    print f
    tag_queue.put(f)

for i in range(4):
    t = TagsMirror(tag_queue)
    t.daemon = True
    t.start()

tag_queue.join()

print "Mirroring other files"
for i in range(2):
    t = ThreadMirror(copy_queue)
    t.daemon = True
    t.start()

copy_queue.join()

print "Done"
