#!/usr/bin/env python
import os, os.path, sys, re, commands, pickle, tempfile, getopt, datetime
import socket, string, random, time, traceback, shutil, popen2

__safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
def shell_quote(s):
    """Quote s so that it is safe for all common shells.
    """
    res = []
    for c in s:
        if c in __safe_chars:
            res.append(c)
        else:
            res.append("=%02x" % ord(c))
    return string.join(res, '')

def shell_unquote(s):
    """Unquote a string quoted by shell_quote.
    """
    if s == "":
        return ""

    frags = string.split(s, "=")
    res = [frags[0]]
    for f in frags[1:]:
        res.append(chr(string.atoi(f[:2], 0x10)))
        res.append(f[2:])
    return string.join(res, '')

def which(filename):
    if not os.environ.has_key('PATH') or os.environ['PATH'] == '':
        p = os.defpath
    else:
        p = os.environ['PATH']
    pathlist = p.split(os.pathsep)
    for path in pathlist:
        f = os.path.join(path, filename)
        if os.access(f, os.X_OK) and not stat.S_ISDIR(os.stat(f)[stat.ST_MODE]):
            return f
    return None

def upakdir():
    if os.getenv('UPAK_HOME'):
        return os.getenv('UPAK_HOME')
    else:
        return os.getenv('HOME') + '/.upak'

def upak_sourcefile():
    return upakdir() + '/sources'

def upak_sourcefileexpanded():
    return upakdir() + '/sources.expanded'

class upak_proxy_mgr:
    def __init__(self):
        proxyfn = os.path.join(upakdir(), 'http_proxy')
        if os.path.exists(proxyfn):
            self.proxy = open(proxyfn).read().strip()
        else:
            self.proxy = None
        self.ignore_urls = {}
    def get_proxy_for_url(self, url):
        if not self.proxy:
            return None
        for u in self.ignore_urls:
            if url.startswith(u):
                return None
        return self.proxy
    def ignore_proxy_for_url(self, url):
        self.ignore_urls[url]=1

class Sources:
    def __init__(self, input_filename, proxy_mgr):
        self.proxy_mgr = proxy_mgr
        ud = upakdir()
        self.sources = []
        self.addsourcefile(input_filename)
    def addsourcefile(self, fn, position=-1, inheritedproxy=None):
        if os.path.exists(fn):
            f = open(fn, 'r')
            while 1:
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                if len(line) == 0:
                    continue
                elif line[0] == '#':
                    continue
                ls = line.split()
                url = ls[0]
                if len(ls) > 1:
                    attrs = ls[1:]
                else:
                    attrs = []
                self.addsource(url, position)
                if position != -1:
                    position += 1
                for attr in attrs:
                    if attr == 'noproxy':
                        self.proxy_mgr.ignore_proxy_for_url(url)
            f.close()
    def addsource(self, source, position):
        if not re.match("^http://.*$", source):
            sys.stderr.write("ERROR: resource %s does not begin with http://...\n" % source)
            sys.exit(1)
        while source[-1] == '/':
            source = source[0:-1]
        if source not in self.sources:
            if position == -1:
                self.sources.append(source)
            else:
                self.sources.insert(position, source)
#        print 'dbg : sources now', self.sources
                
    def __len__(self):
        return len(self.sources)
    def geturl(self, index):
        return self.sources[index]
    def gethash(self, index):
        if index > len(self):
            sys.stderr.write("ERROR: index %d out of range\n" % index)
            sys.exit(1)
        return shell_quote(self.sources[index])
