#!/usr/bin/env bash

dir=`dirname $0`
localedir="$dir/../trunk/locale"
domain="pywinery"

for i in "$localedir/*";
do
    podir="`echo $i`"
    echo -n "Compiling locale in $podir " 
    msgfmt "$podir/LC_MESSAGES/$domain.po" -o "$podir/LC_MESSAGES/$domain.mo"
    echo "
    [ DONE ]"
done
