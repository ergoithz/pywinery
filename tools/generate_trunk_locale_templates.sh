#!/usr/bin/env bash

dir=`dirname $0`
localedir="$dir/locale"
gladefile="$dir/gui.glade"
echo -n "Generating locale template in $podir "
xgettext --sort-output --keyword=translatable -o "$localedir/template.pot" "$gladefile"
echo "
[ DONE ]"
