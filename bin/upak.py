#!/usr/bin/env python

import sys, os, os.path, re, urllib, tarfile, shutil, tempfile
import time, stat, code, socket, string
import fcntl
from sets import Set

from upaklib import *

import sys, linecache
def trace(fr, evt, arg):
    if evt == 'line':
        f = fr.f_code.co_filename
        n = fr.f_lineno
        print '%s:%d -> ' %(f, n), linecache.getline(f, n),
    return trace

quiet_mode = 0
debug_trace = 0
secondary_launch = False
tweak = False

def usage():
    print 'usage:'
    print
    print 'upak [-d] ...  # option that turns on debug mode'
    print 'upak [-q] ...  # option that turns on quiet mode'
    print
    print 'upak update'
    print 'upak list'
    print 'upak installed'
    print 'upak install <package> ...'
    print 'upak [--tweak] install <package> ...'
    print 'upak uninstall <package> ...'
    print
    print 'upak prereq <package> ...'
    print 'upak provides <package> ...'
    print 'upak disable <package> ...'
    print 'upak enable <package> ...'
    print
    print 'upak add-external <packagename> <external_install_directory_prefix>'
    print '# this command adds a package maintained externally, to satisfy'
    print '# dependencies (any needed paths for the external package'
    print '# should be set outside upak).'
    print
    print 'upak import <sources_import_file.txt>'
    print
    print 'upak rebuild-init # rebuilds init files (init.sh, init.csh)'
    print
    print 'upak uninstall-all-packages # forcibly removes all packages'
    print 'upak reinstall-all-packages # reinstalls all non-virtual packages'
    sys.exit(1)

# dir layout:

# ~/.upak
# ~/.upak/sources
# ~/.upak/installed
# ~/.upak/db
# ~/.upak/db/pulls/842713bdfdedda2879a2aacef23bbb3baf940676
# ~/.upak/db/pulls/842713bdfdedda2879a2aacef23bbb3baf940676/pkgfile.tar.gz
# ~/.upak/db/pulls/842713bdfdedda2879a2aacef23bbb3baf940676/packages

def upak_installedname():
    return 'installed'

def upak_installedroot():
    return upakdir() + '/' + upak_installedname()

def upak_db_pulls_dir():
    return upakdir() + '/db/pulls'

proxy_mgr = upak_proxy_mgr()

def upak_add_log(message):
    assert None # not used for now
    f = open(upakdir() + '/runlog', "a")
    f.write(message)
    f.close()

def upak_print_log():
    fn = upakdir() + '/runlog'
    if os.path.exists(fn):
        f = open(fn)
        for line in f.readlines():
            line = line.strip()
            print line
        f.close()
        os.remove(fn)

def upak_commons_dir():
    return os.path.join(upakdir(), 'commons')

def upak_trash_dir():
    return os.path.join(upakdir(), '.trash')

def trash(path):
    tdloc = os.path.join(upak_trash_dir(), `time.time()`)
    shutil.move(path, tdloc)

needed_dirs = [upak_db_pulls_dir(), upak_installedroot(),
               upak_commons_dir(), upak_trash_dir()]
for d in needed_dirs:
    if not os.path.exists(d):
        os.makedirs(d)

# borrowed from Python 2.4
def lexists(path):
    """Test whether a path exists.  Returns True for broken symbolic links"""
    try:
        st = os.lstat(path)
    except os.error:
        return False
    return True

def is_symlink(filename):
    return lexists(filename) and \
           stat.S_ISLNK(os.lstat(filename)[stat.ST_MODE])

def get_installed_packages():
    directories = []
    installed = upak_installedroot()
    if os.path.exists(installed):
        directories = os.listdir(installed)
        directories.sort()
    return directories

def get_installed_packages_nonvirtual():
    packages = get_installed_packages()
    out = []
    for p in packages:
        if not package_is_virtual(p):
            out.append(p)
    return out

def package_is_virtual(pkg):
    fn = os.path.join(upak_installedroot(), pkg)
    assert os.path.exists(fn)
    if is_symlink(fn):
        return 1
    else:
        return 0

def package_installinstructionsdir(pkg):
    for i in range(len(sources)):
        d = os.path.join(upak_db_pulls_dir(), sources.gethash(i),
                         'packages', pkg)
        if os.path.exists(d):
            return d
    return None

def package_installfile(pkg):
    d = package_installinstructionsdir(pkg)
    return d and d + '/inst'

def package_environmentfile(pkg):
    d = package_installinstructionsdir(pkg)
    return d and d + '/environment'

def package_ignorecommonsfile(pkg):
    d = package_installinstructionsdir(pkg)
    return d and d + '/ignore-commons'

def package_prereqfile(pkg):
    d = package_installinstructionsdir(pkg)
    return d and d + '/prereq'

def package_providesfile(pkg):
    d = package_installinstructionsdir(pkg)
    return d and d + '/provides'

# def package_versionfile(pkg):
#     d = package_installinstructionsdir(pkg)
#     return d and d + '/version'

def package_source_url(pkg):
    for i in range(len(sources)):
        hashdir = os.path.join(upak_db_pulls_dir(), sources.gethash(i))
        d = os.path.join(hashdir, 'packages', pkg)
        if os.path.exists(d):
            f = open(os.path.join(hashdir, 'source'))
            out = f.readline().strip()
            f.close()
            return out
    return None

def package_prereqs(pkg):
    out = []
    prereq_file = package_prereqfile(pkg)
    if prereq_file and os.path.exists(prereq_file):
        f = open(prereq_file, 'r')
        for line in f.readlines():
            line = line.strip()
            if len(line)>0 and line[0]!='#':
                out.append(line)
        f.close()
    return out

# return list of prereqs (or empty list)
def package_prereqs_recursive(pkg):
    prereqs = package_prereqs(pkg)
    if prereqs:
        out = prereqs
        for p in prereqs:
            out += package_prereqs_recursive(p)
        return list(Set(out))
    else:
        return []

def package_provides(pkg, include_self=True):
    out = []
    if include_self:
        out = [pkg]
    provides_file = package_providesfile(pkg)
    if provides_file and os.path.exists(provides_file):
        f = open(provides_file, 'r')
        for line in f.readlines():
            line = line.strip()
            if len(line)>0 and line[0]!='#':
                out.append(line)
        f.close()
    return out

def package_installdir(pkg):
    d = upak_installedroot() + '/' + pkg
    if lexists(d):
        return d
    else:
        return None

def package_enabled(pkg):
    fn = os.path.join(upak_installedroot(), pkg)
    if os.path.exists(fn):
        fn2 = os.path.join(fn, '.upak-disabled-mark')
        if os.path.exists(fn2):
            return 1
    return 0

def package_is_installed(pkg):
    instdir = package_installdir(pkg)
    if not instdir:
        sys.stderr.write("ERROR: unknown package %s\n" % pkg)
        sys.exit(1)
    return os.path.exists(instdir)

def find_dirs(dir):
    if not os.path.exists(dir):
        sys.stderr.write("ERROR: %s does not exist\n" % (dir))
        sys.exit(1)
    for root, dirs, files in os.walk(dir, topdown=False):
        for name in dirs:
            fn = os.path.join(root, name)
            yield fn

def find_files(dir):
    if not os.path.exists(dir):
        sys.stderr.write("ERROR: %s does not exist\n" % (dir))
        sys.exit(1)
    for root, dirs, files in os.walk(dir, topdown=False):
        for name in files:
            fn = os.path.join(root, name)
            yield fn

def package_installed_dirs(pkg):
    assert(package_is_installed(pkg))
    oldcwd = os.getcwd()
    out = []
    os.chdir(package_installdir(pkg))
    dotslash_begin = re.compile("^\\./")
    for d in find_dirs('.'):
        if dotslash_begin.search(d):
            d = d[2:]
        out.append(d)
    os.chdir(oldcwd)
    return out

def package_installed_files(pkg):
    assert(package_is_installed(pkg))
    oldcwd = os.getcwd()
    out = []
    os.chdir(package_installdir(pkg))
    upak_begin = re.compile("^\\.upak")
    dotslash_begin = re.compile("^\\./")
    for f in find_files('.'):
        if dotslash_begin.search(f):
            f = f[2:]
        if upak_begin.search(f):
            pass
        else:
            out.append(f)
    os.chdir(oldcwd)
    return out

def install_package(pkg):
    # uninstall old version first, if any
    if pkg in get_installed_packages():
        print 'package',pkg, 'exists, uninstalling first'
        time.sleep(2)
        uninstall_package(pkg)

    if debug_trace:
        print 'install_package(%s)' % (pkg)

    installf = package_installfile(pkg)
    if not os.path.exists(installf):
        sys.stderr.write("ERROR: cannot find %s\n" % (installf))
        sys.exit(1)
    if os.getenv('UPAK_BUILDDIR'):
        d = os.getenv('UPAK_BUILDDIR')
        if not os.access(d,os.F_OK):
            os.mkdir(d)
        pfx = os.path.join(d,'upak-tmp-'+pkg+'-')
    else:
        pfx = 'upak-tmp-' + pkg + '-'
    tempdirname = tempfile.mkdtemp(prefix=pfx)

    delinstallf = False
    if tweak:
        (tempfd, tempfn) = tempfile.mkstemp()
        os.write(tempfd, open(installf).read())
        os.close(tempfd)
        print 'upak: tweaking install script', installf, 'using EDITOR (or vi fallback)'
        if os.getenv('EDITOR'):
            cmd = os.getenv('EDITOR') + ' ' + tempfn
        else:
            cmd = 'vi ' + tempfn
        rc = os.system(cmd)
        if rc:
            raise RuntimeError, 'ERROR: calling %s' % (cmd)
        os.chmod(tempfn, 0700)
        installf = tempfn
        delinstallf = True

    if debug_trace:
        print 'running', installf

    os.environ['TMPDIR'] = tempdirname
    installroot = upak_installedroot()
    os.environ['UPAKINSTALLEDROOT'] = installroot
    installdir = installroot + "/" + pkg
    os.environ['UPAKINSTALLDIR'] = installdir
    os.environ['UPAKWGETURL'] = package_source_url(pkg)
        
    made_directory = None
    if not os.path.exists(installdir):
        os.makedirs(installdir)
        made_directory = installdir
    olddir = os.getcwd()
    os.chdir(tempdirname)
    rc = os.system(installf)
    if delinstallf:
        os.remove(installf)
    if rc != 0:
        sys.stderr.write("ERROR: running %s\n" % (installf))
        if made_directory:
            shutil.rmtree(made_directory, 1)
        sys.stderr.write("ERROR:  failing with install of package %s...not removing temporary directory %s\n" % (pkg, tempdirname))
        sys.exit(1)
    else:
        ignore_commons_fn = package_ignorecommonsfile(pkg)
        if os.path.exists(ignore_commons_fn):
            ignore_commons_f = open(installdir + '/.upak-ignore-commons','w')
            ignore_commons_f.close()
            
        environmentf = package_environmentfile(pkg)
        if os.path.exists(environmentf):
            proc = os.popen(environmentf, 'r')
            if not proc:
                sys.stderr.write("ERROR: failure executing %s\n" % environmentf)
                if made_directory:
                    shutil.rmtree(made_directory, 1)
                sys.stderr.write("ERROR:  failing with install of package %s...not removing temporary directory %s\n" % (pkg, tempdirname))
                sys.exit(1)
            sourceme_sh = open(installdir + '/.upak-sourceme.sh','w')
            sourceme_csh = open(installdir + '/.upak-sourceme.csh','w')
            for l in proc.readlines():
                l = l.strip()
                if len(l) > 0 and l[0] != '#':
                    if len(l.split(' ', 3)) == 3:
                        (instruction, var, val) = l.split()
                        if instruction == 'set':
                            sourceme_sh.write('%s=%s\n' % (var, val))
                            sourceme_sh.write('export %s\n' % (var))
                            sourceme_csh.write('setenv %s %s\n' % (var, val))
                        elif instruction == 'prepend':
                            sourceme_sh.write('%s=%s:$%s\n' % (var, val, var))
                            sourceme_sh.write('export %s\n' % (var))
                            sourceme_csh.write('if ( $?%s ) then\n' % (var))
                            sourceme_csh.write('    setenv %s %s:$%s\n' % (var, val, var))
                            sourceme_csh.write('else\n')
                            sourceme_csh.write('    setenv %s %s\n' % (var, val))
                            sourceme_csh.write('endif\n')
                        elif instruction == 'append':
                            sourceme_sh.write('%s=$%s:%s\n' % (var, var, val))
                            sourceme_sh.write('export %s\n' % (var))
                            sourceme_csh.write('if ( $?%s ) then\n' % (var))
                            sourceme_csh.write('    setenv %s ${%s}:%s\n' % (var, var, val))
                            sourceme_csh.write('else\n')
                            sourceme_csh.write('    setenv %s %s\n' % (var, val))
                            sourceme_csh.write('endif\n')
                        else:
                            sys.stderr.write("ERROR: unknown instruction %s\n" % instruction)
                            sys.exit(1)
                    else:
                        sys.stderr.write("ERROR: unknown line %s\n" % l)
                        sys.exit(1)
            if proc.close() != None:
                sys.stderr.write("ERROR: environment file %s failed\n" % \
                                 environmentf)
                if made_directory:
                    shutil.rmtree(made_directory, 1)
                sys.stderr.write("ERROR:  failing with install of package %s...not removing temporary directory %s\n" % (pkg, tempdirname))
                sys.exit(1)
#                     upak_add_log('NOTE:  package %s set some environment variables.\nIf this is running from an interactive shell, it has received these variable\nsettings, but for any other shells, you should log out and log back in (or\nre-source your shell init file).' % (pkg))
            sourceme_sh.close()
            sourceme_csh.close()

        enable_package(pkg)

    os.chdir(olddir)
    shutil.rmtree(tempdirname)
    if debug_trace:
        print 'install_package(%s) returning' % (pkg)    

def accumulate_provides(packages):
    packages_out = []
    for pkg in packages:
        packages_out.append(pkg)
        provides = package_provides(pkg, False)
        for provided in provides:
            if provided not in packages:
                packages_out.append(provided)
    return packages_out

def accumulate_not_installed_dependencies(packages):
    original_length = len(packages)
    # ensure the same package is not installed more than once in the
    # same execution
    unmentioned_dependencies = Set()
    for pkg in packages:
        dependencies = package_prereqs(pkg)
        for dependency in dependencies:
            if dependency in packages:
                pass
            elif dependency in get_installed_packages():
                pass
            else:
                print 'package %20s depends on not-installed package %s' % (pkg, dependency)
                unmentioned_dependencies.add(dependency)

    if len(unmentioned_dependencies) > 0:
        print 'NOTE:  some additional packages are being installed due to dependencies.'
        print 'Additional packages are:\n'
        sys.stdout.write('%s\n\n' % ','.join(unmentioned_dependencies))
        c = code.InteractiveConsole()
        line = c.raw_input("Proceed? (y or n) ").strip()
        if line == 'y' or line == 'yes':
            pass
        else:
            sys.exit(1)
    return packages + list(unmentioned_dependencies)
    
def accumulate_virtual_providers(packages, virtuals_found_concrete):
    # handle any virtual packages being requested to be installed
    added_packages = []
    for pkg in packages:
        if pkg in virtuals_found_concrete:
            continue
        installdir = package_installinstructionsdir(pkg)

        if not installdir: # it's a virtual package

            # see if it's provided by one of those in 'packages'
            provided_here = False
            for pkg2 in packages:
                if pkg in package_provides(pkg2, False):
                    provided_here = True
                    break
            if provided_here:
                virtuals_found_concrete.add(pkg)
                continue
            
            print "NOTE: package", pkg, \
                  "not found as an installable package, " + \
                  "\n     looking for packages which provide it"
            # scan packages for provides
            candidates = get_candidate_packages()
            suitable_candidates = []
            for c in candidates:
                provides = package_provides(c, False)
                if pkg in provides:
                    suitable_candidates.append(c)
            err = 0
            if len(suitable_candidates) == 0:
                err = 1
            elif len(suitable_candidates) == 1:
                c = code.InteractiveConsole()
                line = c.raw_input(
                    "Install package '%s' which provides %s? (y or n) " % \
                    (suitable_candidates[0], pkg)).strip()
                if len(line) > 0 and line[0] == 'y':
                    added_packages.append(suitable_candidates[0])
                    virtuals_found_concrete.add(pkg)
                else:
                    sys.exit(1)
            else:

                c = code.InteractiveConsole()
                while 1:
                    print "The following candidates provide the package %s:" % (pkg)
                    for i in range(len(suitable_candidates)):
                        print '%2d) %s' % (i+1, suitable_candidates[i]) 
                    line = c.raw_input("Please enter one of them to install, or x to abort: ").strip()
                    if line == 'x':
                        sys.exit(1)
                    elif line.isdigit() and \
                             int(line) <= len(suitable_candidates) and \
                             int(line) > 0:
                        break
                added_packages.append(suitable_candidates[int(line)-1])
                virtuals_found_concrete.add(pkg)
            if err == 1:
                sys.stderr.write("ERROR: unknown package %s\n" % pkg)
                sys.exit(1)
    return packages + added_packages

def install_packages(packages):
    packages_orig = packages
    virtuals_found_concrete = Set([])
    augmented = False
    while 1:
        modified = 0
        packages1 = accumulate_provides(packages)
        if packages != packages1:
            modified = 1
        packages2 = accumulate_not_installed_dependencies(packages1)
        if packages1 != packages2:
            modified = 1
        packages3 = accumulate_virtual_providers(packages2,
                                                 virtuals_found_concrete)
        if packages2 != packages3:
            modified = 1
        packages = packages3
        if not modified:
            break
        else:
            augmented = True

    for v in virtuals_found_concrete:
        packages.remove(v)

    install_order = []
    packages_unplaced = packages[:]
    while len(install_order) < len(packages):
        # look for one with no constraints
        chosen_pkg = None
        for pkg in packages_unplaced:
            prest = Set(packages_unplaced[:])
            prest.remove(pkg)
            provides_added = Set([])
            for p in prest:
                for provide in package_provides(p):
                    provides_added.add(provide)
            prest = provides_added
            pkgdeps = package_prereqs_recursive(pkg)
            need_something_in_rest = False
            for dep in pkgdeps:
                if dep in prest:
                    need_something_in_rest = True
                    break
            if not need_something_in_rest:
                chosen_pkg = pkg
                packages_unplaced.remove(pkg)
                break
        assert chosen_pkg
        install_order.append(chosen_pkg)
    packages = install_order
    if augmented and packages != packages_orig:
        c = code.InteractiveConsole()
        line = c.raw_input(
            "Final list (in order) of concrete packages to install is:\n\n%s\n\nProceed? (y or n) " % \
            (','.join(packages))).strip()
        if line == 'y' or line == 'yes':
            pass
        else:
            sys.exit(1)

    return install_packages_lowlevel(packages)

def install_packages_lowlevel(packages):
    pkg = packages[0]
    if not quiet_mode:
        print '<<< installing', pkg, '>>>'
    install_package(pkg)
    if not quiet_mode:
        print '<<< done installing', pkg, '>>>'
    rebuild_init_files()
    if len(packages) > 1:
        assert sys.executable
        unlock_lockfile()
        cmd = os.path.join(os.path.dirname(sys.argv[0]), 'upak-relaunch.sh')
        args = [cmd, sys.executable, sys.argv[0],
                '-secondary'] + \
                (tweak and ['--tweak'] or []) + \
                (quiet_mode and ['-q'] or []) + \
                (debug_trace and ['-d'] or []) + \
                ['install-lowlevel'] + packages[1:]
        os.execl(cmd, *args)

# turns .upak/sources into .upak/sources.expanded
def update():
    sources_active = Set()
    i = 0
    sourcesnew = Sources(upak_sourcefile(), proxy_mgr)
    while 1:
        if i == len(sourcesnew):
            break
        u = sourcesnew.geturl(i)
        sys.stdout.write('%2d updating from %s...' % (i+1, u))
        sys.stdout.flush()
        url = u + '/packages.tar.gz'
        try:
            pxy = proxy_mgr.get_proxy_for_url(u)
            if pxy:
                pxy={'http':pxy}
            oldenv = None
            if not pxy and os.getenv('http_proxy'):
                oldenv = os.getenv('http_proxy')
                del os.environ['http_proxy']
            fob = urllib.urlopen(url, proxies=pxy)
            if not pxy and oldenv:
                os.environ['http_proxy'] = oldenv
            fob.close()
        except IOError:
            sys.stderr.write("ERROR: cannot retrieve source %s\n" % u)
            sys.exit(1)

        d = sourcesnew.gethash(i)
        sources_active.add(d)
        dir = (upak_db_pulls_dir() + '/' + d);
        dirp = dir + '/packages'
        if not os.path.exists(dir):
            os.makedirs(dir)
        if not os.path.exists(dirp):
            os.makedirs(dirp)
        fn = dir + '/pkgfile.tar.gz'
        pxy = proxy_mgr.get_proxy_for_url(u)
        if pxy:
            pxy={'http':pxy}
        oldenv = None
        if not pxy and os.getenv('http_proxy'):
            oldenv = os.getenv('http_proxy')
            del os.environ['http_proxy']
        fob = urllib.urlopen(url, proxies=pxy)
        if not pxy and oldenv:
            os.environ['http_proxy'] = oldenv
        open(fn,'w').write(fob.read())
        fob.close()
        srcfile = open(dir + '/source', 'w')
        srcfile.write('%s' % (u))
        srcfile.write('\n')
        srcfile.close()
        
        # remove what's already there
        for existing in os.listdir(dirp):
            removeme = dirp + '/' + existing
            shutil.rmtree(removeme, True)

        # expand tarball
        try:
            tf = tarfile.open(fn, 'r')
            while 1:
                ni = tf.next()
                if not ni:
                    break
                if ni.name == '.include':
                    tempdirname = tempfile.mkdtemp()
                    tf.extract(ni, tempdirname)
                    fn = os.path.join(tempdirname, ni.name)
                    inheritedproxy = proxy_mgr.get_proxy_for_url(url)
                    sourcesnew.addsourcefile(fn, i+1, inheritedproxy)
                    os.remove(fn)
                else:
                    tf.extract(ni, dirp)
            tf.close()
        except tarfile.ReadError:
            sys.stderr.write("ERROR: problem unpacking %s\n" % (fn))
            sys.exit(1)
        print 'done'
        i += 1

    if os.path.exists(upak_db_pulls_dir()):
        for hashdir in os.listdir(upak_db_pulls_dir()):
            if hashdir not in sources_active:
                removeme = upak_db_pulls_dir() + '/' + hashdir
                print 'removing', removeme
                shutil.rmtree(removeme, True)

    expanded = open(upak_sourcefileexpanded(), 'w')
    expanded.write('# NOTE: this is a machine generated file via "upak update"!  Do not edit!\n')
    for i in range(len(sourcesnew)):
        url = sourcesnew.geturl(i)
        expanded.write('%s' % url)
        if not proxy_mgr.get_proxy_for_url(url):
            expanded.write(' noproxy')
        expanded.write('\n')

    expanded.close()
        
def list_packages():
    candidates = get_candidate_packages()
    for c in candidates:
        print c

def get_candidate_packages():
    s = Set([])
    if os.path.exists(upak_db_pulls_dir()):
        for hashdir in os.listdir(upak_db_pulls_dir()):
            ls = os.listdir(upak_db_pulls_dir() + '/' + hashdir + '/packages')
            for i in ls:
                s.add(i)
                provides = package_provides(i)
                for p in provides:
                    s.add(p)
    out = []
    for i in s:
        out.append(i)
    out.sort()
    return out

def list_installed_packages():
    old_cwd = os.getcwd()
    os.chdir(upak_installedroot())
    directories = get_installed_packages()
    for p in directories:
        if package_is_disabled(p):
            print p, '(disabled)'
        elif package_is_virtual(p):
            print '%s (virtual link to %s)' % (p, os.readlink(p))
        else:
            print p
    os.chdir(old_cwd)

def uninstall_package(pkg):
    d = package_installdir(pkg)
    if not d or not lexists(d):
        sys.stderr.write("ERROR: uninstalling %s\n" % pkg)
        sys.exit(1)
    print 'removing', d
    if is_symlink(d):
        os.remove(d)
    else:
        commons_unbuild(pkg)
        trash(d)
    installroot = upak_installedroot()
    for d2 in os.listdir(installroot):
        fn = installroot + '/' + d2
        if is_symlink(fn) and os.readlink(fn) == pkg:
            print '    removing', fn, 'as a consequence'
            os.remove(fn)
    rebuild_init_files()
    if os.path.exists(d):
        sys.stderr.write("ERROR: couldn't completely remove %s, you will have to do so manually\n" % (d))
        sys.exit(1)

def uninstall_packages(packages):
    killdep = 0
    installed = get_installed_packages()
    for pkgbyebye in packages:
        provides = package_provides(pkgbyebye)
        for i in installed:
            i_reqs = package_prereqs(i)
            for i_req in i_reqs:
                if i_req in provides and i != pkgbyebye:
                    print 'uninstalling', pkgbyebye, 'would kill dependency', \
                          i, '->', pkgbyebye
                    killdep = 1
    while killdep:
        print 'Proceed? (y or n) ',
        response = sys.stdin.readline().strip()
        if response in ['y','yes']:
            break
        elif response in ['n','no']:
            sys.exit(1)
    for pkg in packages:
        uninstall_package(pkg)
    rebuild_init_files()

def enable_package(pkg):
    instdir = package_installdir(pkg)
    if not instdir:
        sys.stderr.write("ERROR: unknown package %s\n" % pkg)
        sys.exit(1)

    fn = instdir + '/.upak-disabled-mark'
    if os.path.exists(fn):
        os.remove(fn)

    # look at what this package provides
    provides = package_provides(pkg, False)
    olddir = os.getcwd()
    os.chdir(upak_installedroot())
    for p in provides:
        if debug_trace:
            print "package", pkg, "also provides", p
        d = package_installdir(p)
        if d:
            # we will need to override this package.  It better be a symlink
            if is_symlink(d):
                old_provider = os.readlink(d)
                sys.stdout.write('old provider of virtual package %s was %s' \
                                 % (p, old_provider))
                if old_provider == pkg:
                    print
                    disable_package(old_provider)
                else:
                    if old_provider.find('/') != -1:
                        print '...not disabling external provider', old_provider
                        os.remove(d)
                    else:
                        print
                        disable_package(old_provider)
            else:                    
                sys.stderr.write(
                    "ERROR: %s is not a symlink." \
                    "  Since the installed package %s " \
                    "provides the virtual package %s which will be " \
                    "created via a symlink, we cannot proceed." \
                    "  Please manually correct the situation, " \
                    "perhaps by simply deleting %s.\n" % \
                    (d, pkg, p, d))
                sys.exit(1)

        try:
            os.symlink(pkg, p)
        except Exception:
            traceback.print_exc()
            sys.stderr.write("ERROR: os.symlink(%s,%s)\n"%(pkg,p))
            sys.exit(1)

        print 'virtual package', p, 'will now be provided by', pkg
    os.chdir(olddir)
    if not commons_ignored(pkg):
        commons_build(pkg)
    
def disable_package(pkg):
    instdir = package_installdir(pkg)
    if not instdir:
        sys.stderr.write("ERROR: unknown package %s\n" % pkg)
        sys.exit(1)
    if package_is_virtual(pkg):
        sys.stderr.write("ERROR: package %s is virtual, cannot be disabled\n" % (pkg))
        sys.exit(1)
    f = open(instdir + '/.upak-disabled-mark', "w")
    f.close()

    provides = package_provides(pkg, False)
    olddir = os.getcwd()
    os.chdir(upak_installedroot())
    for p in provides:
        d = package_installdir(p)
        if d and is_symlink(d):
            print 'virtual package', p, 'will no longer be provided by', pkg
            os.remove(d)
    os.chdir(olddir)
    commons_unbuild(pkg)

def package_is_disabled(pkg):
    instdir = package_installdir(pkg)
    if not instdir:
        sys.stderr.write("ERROR: unknown package %s\n" % pkg)
        sys.exit(1)
    return os.path.exists(instdir + '/.upak-disabled-mark')

def add_external_package(pkg, installdir):
    if not os.path.exists(installdir):
        sys.stderr.write("ERROR: %s does not exist\n" % installdir)
        sys.exit(1)
    d = package_installdir(pkg)
    if d:
        # we will need to override this package.  It better be a symlink
        if is_symlink(d):
            print d, "is a symlink that we will relocate"
            os.remove(d)
        else:
            sys.stderr.write("ERROR: cannot take over non-virtual package %s\n" %\
                             pkg)
            sys.exit(1)
    olddir = os.getcwd()
    os.chdir(upak_installedroot())
    os.symlink(installdir, pkg)
    os.chdir(olddir)

def get_shell_funcs():
    dirty_mark = (upakdir() + '/dirty-mark')

    upak = os.path.join(os.path.dirname(sys.argv[0]),'upak')
    sh =  "upak() {\n"
    sh = sh + "    %s ${1+\"$@\"}\n" % (upak)
    sh = sh + "    test -f %s && . %s\n" % (dirty_mark, upakdir() + '/init.sh')
    sh = sh + "    test -f %s && /bin/rm -f %s\n" % (dirty_mark, dirty_mark)
    sh = sh + "}\n"

    csh =  "alias upak '"
    csh = csh + "%s \!* ; " % (upak)
    csh = csh + "test -f %s && source %s; " % (dirty_mark, upakdir() + '/init.csh')
    csh = csh + "test -f %s && /bin/rm -f %s; rehash'" % (dirty_mark, dirty_mark)
    return [sh,csh]

def prepend_path_sh(var, dir):
    return '%s=%s:$%s\nexport %s\n' % (var, dir, var, var)

def prepend_path_csh(var, dir):
    s =  'if ( $?%s ) then\n' % (var)
    s += '    setenv %s %s:$%s\n' % (var, dir, var)
    s += 'else\n'
    s += '    setenv %s %s\n' % (var, dir)
    s += 'endif\n'
    return s

def rebuild_init_files():
    master_sh = open(upakdir() + '/init.sh', 'w')
    master_csh = open(upakdir() + '/init.csh', 'w')
    message = '# WARNING:  machine re-generated file, do not edit\n\n'
    master_sh.write('%s' % message)
    master_csh.write('%s' % message)

    (shfunc, cshfunc) = get_shell_funcs()
    master_sh.write('%s\n' % shfunc)
    master_csh.write('%s\n' % cshfunc)

    common_paths = [['PATH','bin'],
                    ['PATH','sbin'],
                    ['MANPATH','man'],
                    ['LD_LIBRARY_PATH', 'lib'],
                    ['LD_LIBRARY_PATH', 'lib64'],
                    ['PKG_CONFIG_PATH', 'lib/pkgconfig'],
                    ['CPATH', 'include'],
                    ['CPATH', 'include/python'],
                    ['LIBRARY_PATH', 'lib'],
                    ['LIBRARY_PATH', 'lib64'],
                    ['PYTHONPATH', 'lib/python']]

    separate_paths = [['INFOPATH','info']]

    message = '\n# common paths\n'
    master_sh.write(message)
    master_csh.write(message)
    for path in common_paths:
        var = path[0]
        dir = os.path.join(upak_commons_dir(), path[1])
        if os.path.exists(dir):
            master_sh.write(prepend_path_sh(var,dir))
            master_csh.write(prepend_path_csh(var,dir))

    message = '\n# package-specific paths\n'
    master_sh.write(message)
    master_csh.write(message)

    packages = get_installed_packages_nonvirtual()
    packages.reverse()
    for pkg in packages:
        pkgroot = package_installdir(pkg)
        message = '# package ' + pkg + '\n'
        master_sh.write(message)
        master_csh.write(message)
        if package_is_disabled(pkg):
            pass
        else:
            if commons_ignored(pkg):
                for path in common_paths:
                    var = path[0]
                    dir = os.path.join(pkgroot, path[1])                   
                    if os.path.exists(dir):
                        if var != 'LD_LIBRARY_PATH' or \
                                len([x for x in os.listdir(dir) if re.search("\\.so", x)]) > 0:
                            master_sh.write(prepend_path_sh(var, dir))
                            master_csh.write(prepend_path_csh(var, dir))

            for path in separate_paths:
                var = path[0]
                dir = os.path.join(pkgroot, path[1])
                if os.path.exists(dir):
                    master_sh.write(prepend_path_sh(var, dir))
                    master_csh.write(prepend_path_csh(var, dir))

            shfile = pkgroot + '/.upak-sourceme.sh'
            cshfile = pkgroot + '/.upak-sourceme.csh'
            if os.path.exists(shfile):
                master_sh.write('. %s\n' % (shfile))
            if os.path.exists(cshfile):
                master_csh.write('source %s\n' % (cshfile))
    master_sh.close()
    master_csh.close()

    # let shell functions know to re-read it
    f = open(upakdir() + '/dirty-mark','w')
    f.close()

def uninstall_all_packages( ):
    removal_dirs = [upak_installedroot(), upak_commons_dir()]
    print 'About to completely remove the dirs:'
    for d in removal_dirs:
        print '    ', d
    print 'Please confirm you want to uninstall all packages in this way (y or n): ',
    response = sys.stdin.readline().strip()
    if response == 'y' or response == 'yes':
        for d in removal_dirs:
            trash(d)
        rebuild_init_files()
    else:
        print 'Taking no action.'

def reinstall_all_packages( ):
    packages = get_installed_packages_nonvirtual()
    print 're-installing packages: ', ' '.join(packages)
    print 'Please confirm you want to reinstall these packages (y or n): ',
    response = sys.stdin.readline().strip()
    if response == 'y' or response == 'yes':
        pass
    else:
        print 'Taking no action.'
        sys.exit(1)
    uninstall_packages(packages)
    install_packages(packages)

def import_source(add_this_file):
    sourcefile = upak_sourcefile()
    if not os.path.exists(add_this_file):
        sys.stderr.write("ERROR: file %s does not exist" % (add_this_file))
        sys.exit(1)
    fout = open(sourcefile, "a")
    f = open(add_this_file, "r")
    for line in f:
        line = line.strip()
        if len(line) > 0 and line[0] != '#' and line not in sources.sources:
            fout.write('%s\n' % (line))
    fout.close()
    f.close()

commons_merged_dirs = ['bin','etc','include','lib','lib64','libexec','man','sbin','share','var']

def commons_matches_merged_dir(fn):
    for d in commons_merged_dirs:
        if fn.startswith(d):
            return 1
    return 0

def commons_ignored(pkg):
    return os.path.exists(
        os.path.join(package_installdir(pkg),'.upak-ignore-commons'))

def commons_build(pkg):
    print 'enabling common symlinks for', pkg
    old_cwd = os.getcwd()
    dirs = package_installed_dirs(pkg)
    files = package_installed_files(pkg)
    os.chdir(upak_commons_dir())
    for d in dirs:
        if commons_matches_merged_dir(d) and not os.path.exists(d):
            os.makedirs(d)
    for f in files:
        os.chdir(upak_commons_dir())
        dir, base = os.path.dirname(f), os.path.basename(f)
        if dir and commons_matches_merged_dir(dir):
            os.chdir(dir)
            linknm = '../' * (2 + dir.count('/')) + 'installed/' + pkg + '/' + f
            if os.path.exists(base):
                existing_target = os.readlink(base)
                while 1:
                    if os.path.dirname(existing_target).endswith('installed'):
                        existing_target = os.path.basename(existing_target)
                        break
                    existing_target = os.path.dirname(existing_target)
                sys.stderr.write("ERROR: file %s in the symlink tree already exists, owned by "
                                 "package %s.\nEvidently package %s and %s "
                                 "conflict,\nalthough this is not reflected "
                                 "in the package database.\nPlease uninstall "
                                 "package %s manually and try again.\n" % \
                                 (f, existing_target, pkg, existing_target,
                                  existing_target))
                sys.exit(1)
            os.symlink(linknm, base)
    os.chdir(old_cwd)

def commons_unbuild(pkg):
    print 'disabling common symlinks for', pkg
    old_cwd = os.getcwd()
    dirs = package_installed_dirs(pkg)
    files = package_installed_files(pkg)
    os.chdir(upak_commons_dir())
    for f in files:
        os.chdir(upak_commons_dir())
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass
    for d in dirs:
        if commons_matches_merged_dir(d) and os.path.exists(d):
            try:
                os.rmdir(d)
            except Exception:
                pass
    os.chdir(old_cwd)

def commons_rebuild_all():
    trash(upak_commons_dir())
    os.mkdir(upak_commons_dir())
    pkgs = get_installed_packages_nonvirtual()
    for pkg in pkgs:
        if not commons_ignored(pkg) and not package_is_disabled(pkg):
            commons_build(pkg)

def upak_gc():
    shutil.rmtree(upak_trash_dir(), True)
    if not os.path.exists(upak_trash_dir()):
        os.mkdir(upak_trash_dir())
        
lock_fd = None

def lock_lockfile():
    lock_file = upakdir() + "/lock"
    global lock_fd
    lock_fd = -1
    if not os.path.exists(lock_file):
        f = open(lock_file, "w")
        f.write("this is a upak internally-used lock file, do not edit!\n")
        f.close()
    try:
        lock_fd = os.open(lock_file, os.O_WRONLY)
        fcntl.lockf(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        sys.stderr.write("ERROR: upak: acquiring lock on %s, is another upak instance running?\n" % (socket.gethostname()))
        sys.exit(1)

def unlock_lockfile():
    try:
        global lock_fd
        fcntl.lockf(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
        lock_fd = None
    except Exception:
        sys.stderr.write("ERROR: unlocking lock\n")
        sys.exit(1)

sources = Sources(upak_sourcefileexpanded(), proxy_mgr)

if __name__ == "__main__": # when run as a script
    if not os.path.exists(upakdir()):
        print 'INFO: making directory', upakdir()
        os.mkdir(upakdir())

    if not os.path.exists(upakdir() + '/init.sh'):
        print 'INFO: making new upak init files.'
        rebuild_init_files()
        print 'You should now add a line like'
        print '    . %s/init.sh       # load upak for bourne shell and derivatives' % (upakdir())
        print 'OR'
        print '    source %s/init.csh # load upak for C shell and derivatives' % (upakdir())
        print 'to your shell initialization file.'
        print ''
        print 'Once that is done, and you have logged out and logged back in, rerun upak.'
        sys.exit(1)

    if ((len(sys.argv)-1) == 0):
        usage()

    # lock to ensure 1 instance is running at once
    lock_lockfile()

    while 1:
        if sys.argv[1] == "-d":
            debug_trace = 1
            sys.settrace(trace)
        elif sys.argv[1] == '-q':
            quiet_mode = 1
        elif sys.argv[1] == '-secondary':
            secondary_launch = True
        elif sys.argv[1] == '--tweak':
            tweak = True
        else:
            break
        sys.argv = sys.argv[:1] + sys.argv[2:]

    command = sys.argv[1]
    if (command == 'update'):
        if (len(sys.argv) != 2):
            usage()
        update()
    elif (command == 'install'):
        if (len(sys.argv) < 3):
            usage()
        install_packages(sys.argv[2:])
    elif (command == 'install-lowlevel'):
        if (len(sys.argv) < 3):
            usage()
        install_packages_lowlevel(sys.argv[2:])
    elif command == 'list':
        list_packages()
    elif command == 'uninstall':
        if (len(sys.argv) < 3):
            usage()
        uninstall_packages(sys.argv[2:])
    elif command == 'installed':
        list_installed_packages()
    elif command == 'prereq':
        for i in sys.argv[2:]:
            print 'package', i, 'depends on', ','.join(package_prereqs(i))
    elif command == 'provides':
        for i in sys.argv[2:]:
            print 'package', i, 'provides', ','.join(package_provides(i))
    elif command == 'disable':
        for i in sys.argv[2:]:
            disable_package(i)
        rebuild_init_files()
    elif command == 'enable':
        for i in sys.argv[2:]:
            enable_package(i)
        rebuild_init_files()
    elif command == 'rebuild-init':
        rebuild_init_files()
    elif command == 'add-external':
        if len(sys.argv) != 4:
            usage()
        add_external_package(*sys.argv[2:])
    elif command == 'uninstall-all-packages':
        if len(sys.argv) != 2:
            usage()
        uninstall_all_packages()
    elif command == 'reinstall-all-packages':
        if len(sys.argv) != 2:
            usage()
        reinstall_all_packages()
    elif command == 'import':
        if len(sys.argv) != 3:
            usage()
        import_source(sys.argv[2])
    elif command == 'files':
        for f in package_installed_files(sys.argv[2]):
            print f
    elif command == 'dirs':
        for d in package_installed_dirs(sys.argv[2]):
            print d
    elif command == 'rebuild-commons':
        commons_rebuild_all()
    else:
        print "command " + command + " not implemented"

    upak_gc()

    unlock_lockfile()
            
