#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

import sys
import os.path
import logging

from . import wineVersion, Main, logger

if __name__ == "__main__":
    logger.addHandler(logging.StreamHandler())

    args = sys.argv[1:]
    cmd = sys.argv[0]

    if "--help" in args or "-h" in args:
        print('''%(cmd)s - easy graphical tool for wineprefixing.
Usage:
    %(cmd)s [OPTIONS...] COMMAND [ARGUMENTS...]

Options:
    -v, --version     Prints Wine and Pywinery's version.
    -x, --nogui       Run with autodetected prefix if possible.
    -f, --force-ask   Show dialog whether given executable is known or doesn't.
    -d, --debug       Show's wine debug messages.
    -h, --help        Show this help.
''' % locals())
    elif "--version" in args or "-v" in args:
        print("%s-%s; %s" % (
            os.path.basename(cmd),
            ".".join(str(i) for i in __version__),
            wineVersion() or "wine not found in PATH.")
            )
    else:
        Main().run(sys.argv)
