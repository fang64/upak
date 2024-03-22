This is the upak README file.

upak stands for User PAcKage manager, and is a system for automating
the download, configuration, building, and installation of a package
via a regular non-root user.  It targets the experienced UNIX user.

It is patterned after my experience with debian's package managers
apt-get and dpkg and FreeBSD's ports system.

DOWNLOADING
-----------
You should be able to download the latest release from

http://bmi.osu.edu/~rutt/upak.html

INSTALL
-------
The install begins by downloading upak-VERSION.tar.gz.
Next, untar the file you downloaded:

    tar xzvf upak-VERSION.tar.gz

Next, add the resulting upak-VERSION/bin directory to your path using
your shell specific means of doing so.

Then, run the command 'upak' with no arguments.  The first time you
run upak, you may be asked to install a more recent version of Python,
if /usr/bin/python and /usr/local/bin python are too old (answer 'y'
to proceed with download, build and installation of a newer version).
After that, you'll see a message informing you to add a single line to
your shell start up file (~/.bashrc, ~/.cshrc, etc.).  In general the
line will look like the following:

    . $HOME/.upak/init.sh       # for Bourne shell derivatives

OR
    
    source $HOME/.upak/init.csh # for C shell derivatives

After you have added that line, logout and log back in.  Finally,
you'll need to install some upak sources, which contain pointers to
installable packages.  The relevant configuration file is
~/.upak/sources; it contains a list of URLs, one per line.  You can
use the following command as a starting point to pick up my personal
packages:

    echo http://bmi.osu.edu/~rutt/resources/upak/benjamin-rutt > $HOME/.upak/sources

Finally, upak will store its package databases and installation trees
at ~/.upak by default.  If you would like to change this location, set
the environment variable UPAK_HOME, and source the file
$UPAK_HOME/init.sh in your shell startup file instead of
$HOME/.upak/init.sh.
    
REQUIREMENTS
------------
upak relies on a relatively recent python installation (versions 2.3
and on should do fine).  If such a version is not available in your
path, the first time you run upak, it will, with your permission, download
python version 2.3 and use that version in the future to run upak.

upak also depends on the following executables to be present on your system:

    -/bin/sh (Bourne shell)
    -a C compiler
    -wget
    -sleep
    -gunzip
    -bzcat
    -tar
    -make
    -mktemp

All these should be available on a reasonable Linux installation.

upak should run on other POSIX platforms as long as they have the above
utilities.

Some of the user-supplied packages may require other things, such as a
C++ compiler, etc. but hopefully these are installed as well.

USAGE
-----

To learn how to use upak, you can issue the following command:

    $ upak
   
Once you can run upak with no arguments without error, as the next
step (or anytime you adjust the ~/.upak/sources file) you should
update its view of what packages can be installed:

    $ upak update

You may want to re-run the update command occasionally, in case any
new packages have been added, or updated.
    
To install something you'll do something like:

    $ upak install <packagename>

Which will download, build, and install the package for you
automatically.  There is nothing more you'll need to do to start using
the package, it will be in your path at this point (in this particular
login shell, at least; if you run other shells, you should log them
out and log back in to realize the changes).  Sometimes, you may be
asked to answer questions during the install to help configure the
package, but I try to automate all that I can when I am designing the
automated package installs.

To learn what packages are available to install, you can issue the
following command:

    $ upak list

To see what packages are installed already, you can issue the
following command:

    $ upak installed
    
To uninstall a package, you can issue the following command:

    $ upak uninstall <package-name>

If you really want to tweak the install process for a package to do
something custom, you can use something like:

    $ upak --tweak install <packagename>

which will fire up your EDITOR (or vi) and allow you to adjust the way
the software is built (e.g. passing some optional flags to ./configure).
    
There are a number of other commands, just type 'upak' with no
arguments to see some of them.

To alter the build working dir (in case /tmp is low on disk space) you
can set environment variable UPAK_BUILDDIR to something like
$HOME/tmp.

PACKAGES
--------

Where to find packages to place in ~/.upak/sources ?  You can use
my personal packages list, made available at
http://bmi.osu.edu/~rutt/resources/upak/benjamin-rutt

BUGS/CONTACT
------------
Contact information/bugs/flames:  Benjamin Rutt <rutt@bmi.osu.edu>
Web site:                         http://bmi.osu.edu/~rutt/upak.html
