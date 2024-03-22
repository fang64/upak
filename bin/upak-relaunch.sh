#! /bin/sh

if [ "x$UPAK_HOME" = "x" ]; then
    UPAK_HOME=$HOME/.upak
    export UPAK_HOME
fi
. $UPAK_HOME/init.sh
${1+"$@"}
