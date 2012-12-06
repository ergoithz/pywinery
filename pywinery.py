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
__app__ = "pywinery"
__version__ = (0, 3, 0)
__author__ = "Felipe A. Hernandez <spayder26@gmail.com>"

from os import environ, listdir, sep, linesep, kill  as os_kill, getuid,\
    getgid, remove, mkdir, symlink, access, X_OK

import sys
import os
import os.path
import subprocess
import logging
import locale
import struct
import functools
import operator
import time

from gi.repository import Gtk, Gdk, GLib, Gio, GdkPixbuf

# App config
app_path = os.path.dirname(os.path.abspath(__file__))
#sys.path.insert(0, app_path)

PREFIX_PATH = "$HOME/.local/share/wineprefixes" # prefix path by bottlespec

# Locale setup
locale_path = os.path.join(app_path, "locale")
locale_domain = __app__
locale.setlocale(locale.LC_ALL, "")
locale.bindtextdomain(locale_domain, locale_path)
locale.textdomain(locale_domain)
_ = locale.gettext

# Trash pipe for subproccess functions
DEVNULL = open(os.devnull, "a")

# Environ with no lang (for output parsing)
CENV = environ.copy()
CENV["LANG"] = "c"

# ELF header struct
ELF = struct.Struct("=4sBBBBBxxxxxxx")

def elfarch(path):
    elfclass = 0
    f = None
    try:
        f = open(path, "rb")
        magic, elfclass, endianness, version, os_abi, abi_version = ELF.unpack(f.read(ELF.size))
    except struct.error as e:
        logging.error("Wrong file format on %s" % path, extra={"exception":e})
    finally:
        if f:
            f.close()
    return 64 if elfclass else 32

def alternative_if_exists(path):
    ''' Receives a path and returns an alternative if alredy exists '''
    temptative = path = os.path.expandvars(path)
    counter = 1
    while os.path.exists(temptative):
        counter += 1
        temptative = "%s_%d" % (path, counter)
    return temptative

def move_to_trash(path):
    Gio.File.new_for_path(path).trash(None)

# Enviroment's detection and actions
def getBin(name):
    try:
        return subprocess.check_output(
            ("which", name), env=CENV, stderr=DEVNULL
            ).strip() or None
    except subprocess.CalledProcessError:  # Non-zero rcode
        return None

def checkBin(name):
    if os.path.exists(name) and access(name, X_OK):
        return True
    return bool(getBin(name))

def wineVersion():
    if not checkBin("wine"):
        return None
    try:
        return subprocess.check_output(
            ("wine", "--version"), env=CENV, stderr=DEVNULL
            ).strip() or None
    except subprocess.CalledProcessError:  # Non-zero rcode
        return None

def legacy_to_bottlespec(defaults):
    '''
    Moves old legacy configuration to new bottlespec format
    '''
    newdir = os.path.expandvars("$HOME/.local/share/wineprefixes")
    configdir = os.path.expandvars("$HOME/.config/pywinery")
    old =  os.path.join(configdir, "prefixes.config")
    if os.path.isfile(old):
        # Load prefixes with exe lists
        f = open(old,"r")
        configlines = {}
        lastconfigline = None
        for i in f.readlines():
            si = i.strip()
            if si:
                if si[0]==">":
                    if lastconfigline:
                        configlines[lastconfigline].append(si[1:].strip())
                else:
                    lastconfigline = si
                    configlines[si] = []
        f.close()

        # Skip prefixes already in newdir but update cfg with execs
        for i in listdir(newdir):
            rpath = os.path.realpath(os.path.join(newdir, i))
            for j in configlines.keys():
                if os.path.realpath(j) == rpath:
                    prefix = Prefix(rpath, defaults)
                    prefix.known_executables.extend(
                        i for i in configlines[j]
                        if not i in prefix.known_executables
                        )
                    del configlines[j]

        # Newdir prefix linking
        for key, values in configlines.iteritems():
            if os.path.isdir(key): # We cannot import broken prefixes
                end = key.split(sep)[-1]
                prefix = Prefix(key, defaults)
                prefix["ww_name"] = end
                prefix.known_executables.extend(values)
                prefix.save()
        os.remove(old)

class CallbackList(list):
    __modifiers__ = {
        "__delitem__", "__delslice__", "__iadd__", "__imul__", "append",
        "extend", "insert", "pop", "remove", "reverse", "sort"
        }
    def __wrapper__(self, fnc, cb, *args, **kwargs):
        fnc(*args, **kwargs)
        cb(self)

    def __init__(self, v=(), cb=None):
        list.__init__(self, v)
        if cb:
            for attr in dir(self):
                if callable(getattr(self, attr)) and attr in self.__modifiers__:
                    wrapped = functools.partial(self.__wrapper__, getattr(self, attr), cb)
                    setattr(self, attr, wrapped)

class ExeInfoExtractor(object):
    '''
    Try to extract the icon from a exe resources.
    '''
    def __init__(self):
        self._wrestool = getBin("wrestool")
        self._info_cache = {}

    def extract(self, path):
        pass

    def get_from_cache(path):
        pass

class ExeIconExtractor(object):
    '''
    Try to extract the icon from a exe resources.
    '''
    def __init__(self):
        self._wrestool = getBin("wrestool")
        self._theme = Gtk.IconTheme.get_default()
        self._pixbuf_cache = {}
        self._default_icon_cache = {}

    def _default_icon(self, path, icon_size):
        if icon_size in self._default_icon_cache:
            return self._default_icon_cache[icon_size]
        try:
            content_type, uncertain = Gio.content_type_guess(path, None)
            gicon = Gio.content_type_get_icon(content_type)
            icon = self._theme.lookup_by_gicon(gicon, icon_size, 0).load_icon()
        except BaseException as e:
            # Bug in GTK
            logging.exception(e)
            icon = self._theme.load_icon("gtk-missing-image", icon_size, 0)
        self._default_icon_cache[icon_size] = icon
        return icon

    def extract(self, path, icon_size):
        if (path, icon_size) in self._pixbuf_cache:
            return self._pixbuf_cache[path, icon_size]
        elif self._wrestool is None:
            return self._default_icon[path, icon_size]
        try:
            resources = subprocess.check_output(
                (self._wrestool, "-l", path),
                env=CENV, stderr=DEVNULL
                ).strip().splitlines()
        except subprocess.CalledProcessError: # Non-zero rcode
            fallback = self._default_icon(path, icon_size)
            self._pixbuf_cache[path, icon_size] = fallback
            return fallback

        images = {}
        dist = sys.maxint
        size = 0
        result = None
        for rline in resources:
            if "--type=14" in rline:
                line = dict( # Parsing line
                    i.strip("[]").split("=", 1) if "=" in i else (i.strip("[]"), None)
                    for i in rline.split() if i)
                try:
                    data = subprocess.check_output(
                        (self._wrestool, "-x", "--name=%(--name)s" % line, path),
                        env=CENV, stderr=DEVNULL
                        ).strip()
                    if not data:
                        continue
                except subprocess.CalledProcessError: # Non-zero rcode
                    continue
                except KeyError:
                    continue
                except BaseException as e:
                    logging.exception(e)
                    continue
                try:
                    loader = GdkPixbuf.PixbufLoader.new_with_mime_type("image/x-icon")
                    loader.write(data)
                    loader.close()
                    pixbuf = loader.get_pixbuf()
                except GLib.GError: # Glib cannot handle compressed icons
                    loader.close()
                    continue
                except BaseException as e:
                    loader.close()
                    logging.exception(e)
                    continue
                picon_size = (pixbuf.get_height() + pixbuf.get_width()) / 2
                psize = int(line["size"])
                pdist = abs(icon_size - picon_size)
                if pdist < dist or pdist == dist and size < psize:
                    # Best size fit or equal size fit but better quality
                    size = psize
                    dist = pdist
                    result = pixbuf
        if dist == sys.maxint:
            toreturn = self._default_icon(path, icon_size)
        elif dist:
            toreturn = result.scale_simple(icon_size, icon_size, GdkPixbuf.InterpType.HYPER)
        else:
            toreturn = result
        self._pixbuf_cache[path, icon_size] = toreturn
        return toreturn

    def get_from_cache(self, path, icon_size):
        '''
        Return only a cache icon, or a fallback one.
        '''
        return self._pixbuf_cache.get((path, icon_size), self._default_icon(path, icon_size))

# FIXME(spayder26): remove when fixed
# User xrandr to protect desktop resolution from bug
# http://bugs.winehq.org/show_bug.cgi?id=10841
# http://wiki.winehq.org/FAQ#head-acb200594b5bcd19722faf6fd34b60cc9c2f237b
class ResolutionFixer(object):
    def __init__(self):
        self._xrandr = getBin("xrandr")
        self._resolutions = {}

    def get_resolutions(self):
        if self._xrandr is None:
            return
        lines = subprocess.check_output(
            (self._xrandr, "--query"),
            env=CENV, stderr=DEVNULL
            ).splitlines()
        current_screen = None
        current_resolution = None
        for line in lines:
            if line.startswith("Screen"):
                if current_screen:
                    yield current_screen, current_resolution
                screen, data = line.split(":")
                current_screen = int(screen.split()[-1])
                current_resolution = [None, None]
            else:
                line = line.strip().split()
                if "+" in line[-1]:
                    current_resolution[0] = tuple(int(i) for i in line[0].split("x"))
                if "*" in line[-1]:
                    current_resolution[1] = tuple(int(i) for i in line[0].split("x"))
        if not current_screen is None:
            yield current_screen, current_resolution

    def clear(self):
        self._resolutions.clear()

    def backup(self):
        if self._xrandr and not self._resolutions:
            self._resolutions.update(self.get_resolutions())

    def restore(self):
        if self._xrandr is None:
            return
        for screen, (currsize, realsize) in self.get_resolutions():
            oldcurrsize, oldrealsize = self._resolutions.get(screen, (currsize, realsize))
            if currsize == oldcurrsize and realsize == oldrealsize:
                continue
            width, height = oldcurrsize
            try:
                subprocess.check_call(
                    (self._xrandr, "--screen", "%d" % screen, "--size", "%dx%d" % (width, height)),
                    env=CENV, stderr=DEVNULL
                    )
            except BaseException as e:
                logging.exception(e)

def newline(fileobj):
    '''
    Detects the line separator from fileobj
    '''
    newlinechar = None
    if hasattr(fileobj, "newlines"):
        if isinstance(fileobj.newlines, tuple):
            newlinechar = fileobj.newlines[-1]
        else:
            newlinechar = fileobj.newlines
    if newlinechar is None:
        return os.linesep
    return newlinechar

class Prefix(object):
    '''
    Prefix abstraction class

    wrapper.cfg variables are accessible using __getitem__ and __setitem__
    interfaces.

    '''
    _icon = Gtk.STOCK_HARDDISK
    @property
    def icon(self):
        return self._icon

    @property
    def name(self):
        return self["ww_name"] or os.path.basename(self.path)

    @name.setter
    def name(self, x):
        self["ww_name"] = x

    _arch = None
    @property
    def arch(self):
        if self._arch is None:
            path = os.path.join(self._path, "system.reg")
            if os.path.isfile(path):
                f = open(path, "r")
                head = f.read(1024)
                lns = newline(f)
                f.close()
                if ("%s#arch=win64" % lns) in head:
                    self._arch = "win64"
                else:
                    self._arch = "win32"
            elif self["ww_arch"] in ("win32", "win64"):
                self._arch = self["ww_arch"]
            elif self.winepath:
                self._arch = elfarch(self.winepath)
            else:
                return "win32"
        return self._arch

    # Architecture must be win32 or win64
    _supported_architectures = ("win32","win64")
    @arch.setter
    def arch(self, x):
        # WINE BUG WORKAROUND (cannot set arch if folder exists)
        if os.path.isdir(self._path):
            # FIXME(spayder26): remove when fixed
            return
        #if os.path.isfile(os.path.join(self._path, "system.reg")):
        #    # Architecture cannot be changed after prefix generation
        #    return
        if not x in self._supported_architectures:
            return
        self["ww_arch"] = x
        self._arch = x

    @property
    def path(self):
        return self._path

    @property
    def wineserverpath(self):
        tr = self["ww_wineserver"]
        if tr:
            return self.unrelativize(tr)
        return None

    @wineserverpath.setter
    def wineserverpath(self, x):
        if x:
            self["ww_wineserver"] = self.relativize(x)
        else:
            self["ww_wineserver"] = self._defaults["ww_wineserver"]

    @property
    def winepath(self):
        tr = self["ww_wine"]
        if tr:
            return self.unrelativize(tr)
        return None

    @winepath.setter
    def winepath(self, x):
        if x:
            self["ww_wine"] = self.relativize(x)
        else:
            self["ww_wine"] = self._defaults["ww_wine"]

    _known_executables = None
    @property
    def known_executables(self):
        if self._known_executables is None:
            if self["ww_known_executables"]:
                known = (
                    self.unrelativize(i.replace("\0", ":")) # Unescape escaped colons
                    for i in self["ww_known_executables"]
                        .replace("\\\\","\1") # Escape escaped slashes
                        .replace("\\:", "\0") # Escape escaped colons
                        .replace("\1","\\") # Unescape escaped slashes
                        .split(":")
                    )
            else:
                known = ()
            self._known_executables = CallbackList(known, self._update_known_executables)
        return self._known_executables

    @property
    def ignore(self):
        return self["ww_ignore"] == "1"

    @ignore.setter
    def ignore(self, x):
        self["ww_ignore"] = "1" if x else None

    @property
    def imported(self):
        return os.path.islink(self._path)

    @property
    def winemenubuilder_disable(self):
        return self["ww_winemenubuilder_disable"] == "1"

    @winemenubuilder_disable.setter
    def winemenubuilder_disable(self, x):
        self["ww_winemenubuilder_disable"] = "1" if x else None

    @property
    def ready(self):
        '''
        True if prefix can run executables
        '''
        return os.path.isdir(self._path)

    @property
    def running_commands(self):
        return self._runningcount

    callback = None
    def __init__(self, path, defaults):
        if not os.path.isabs(path):
            path = os.path.join(os.path.expandvars(PREFIX_PATH), path)
        self._path = path
        self._config = os.path.join(path, "wrapper.cfg")
        self._defaults = defaults
        self._cache = {} # Config cache
        self._unsaved = [] # Unsaved changes

    def __del__(self):
        if self._unsaved:
            self._first_save()

    def __repr__(self):
        return "<%s:%s>" % (self.__class__.__name__, self.name)

    def __setitem__(self, x, y):
        '''
        __setitem__ wrapper to wrapper.cfg
        '''
        # Prevent write the same value
        if x in self._cache:
            if self._cache[x] == y:
                return
        elif x in self._defaults and y == self._defaults[x]:
            return

        found = False
        del_item = False
        if x in self._defaults and y == self._defaults[x]:
            # Removal if value is default
            if x in self._cache:
                del self._cache[x]
            del_item = True
        else:
            # Cache update
            self._cache[x] = y

        if x.startswith("ww_"):
            # wrapper.cfg parsing
            if os.path.isfile(self._config):
                f = open(self._config, "r")
                data = f.readlines()
                newlinechar = newline(f)
                f.close()
            else:
                data = self._unsaved
                newlinechar = os.linesep

            # Inline value substitution
            for n, line in enumerate(data):
                if line.split("=")[0] == x:
                    if del_item:
                        if "#" in line:
                            # preserve comment
                            data[n] = "#%s" % line.split("#", 1)[-1]
                        else:
                            data.pop(n)
                    else:
                        comment = ""
                        if "#" in line:
                            # preserve comment
                            precomment, comment = line.split("#", 1)
                            spaces = len(precomment)-len(precomment.rstrip())
                            comment = "%s#%s" % (" "*spaces, comment[:-1])
                        data[n] = "%s=\"%s\"%s%s" % (
                            x, # variable
                            y.replace("\"","\\\""), # value with escaped quotes
                            comment, # inline comment (if any)
                            newlinechar)
                    break
            else: # line not found
                if not del_item:
                    # new line with value
                    data.append("%s=\"%s\"%s" % (
                        x, # variable
                        y.replace("\"","\\\""), # value with escaped quotes
                        newlinechar))
            self._write(data)

    def __getitem__(self, x):
        if x in self._cache:
            return self._cache[x]
        elif x.startswith("ww_") and os.path.isfile(self._config):
            f = open(self._config, "r")
            data = f.readlines()
            f.close()
            for line in data: # We cache all data
                if "=" in line:
                    key, value = line.split("=")
                    if "#" in key:
                        continue
                    elif "#" in value:
                        value = value.split("#",1)[0]
                    # Key, value parsing
                    key = key.strip()
                    value = value.strip()
                    if value[0] == value[-1] and value[0] in "\"'":
                        # quoted value, needs to unescape quotes
                        value = value[1:-1].replace("\\%s" % value[0], value[0])
                    else:
                        # unquoted value
                        value = value.replace("\\ ", " ") # Unescape spaces
                    self._cache[key] = value
            if x in self._cache:
                return self._cache[x]
        if x in self._defaults:
            return self._defaults[x]
        raise KeyError("No variable with name %s." % x)

    def _write(self, lines=None):
        '''
        Write full config file with given lines
        '''
        # Try to save lines
        if os.path.isdir(self._path):
            logging.debug("Config written for %s." % self.name)
            f = open(self._config, "w")
            f.writelines(lines)
            f.close()
            if self._unsaved:
                del self._unsaved[:]
        # Run callback
        if self.callback:
            self.callback(self)

    def _update_known_executables(self, exelist):
        self["ww_known_executables"] = ":".join(i.replace(":","\\:") for i in exelist)

    _runningcount = 0
    _resolution_fixer = None
    def _fixes_initialize(self, command):
        if self._resolution_fixer is None:
            self._resolution_fixer = ResolutionFixer()
        self._resolution_fixer.backup()
        self._runningcount += 1

    def _fixes_watch(self, popen):
        rcode = popen.poll()
        if rcode is None:
            pass
        else:
            self._resolution_fixer.restore()
            self._resolution_fixer.clear()
            self._runningcount -= 1
            return False
        return True

    def relativize(self, path):
        path = os.path.abspath(path)
        home = environ["HOME"]
        if home[-1] == sep:
            home = home[:-1]
        for old, new in ((self.path, ""), (os.path.realpath(self.path), ""), (home, "$HOME")):
            if path.startswith(old):
                return "%s%s%s" % (new, sep if new else "", path[len(old)+1:])
        return path

    def unrelativize(self, path):
        path = os.path.expandvars(path)
        return path if os.path.isabs(path) else os.path.join(self.path, path)

    def wine(self, command, env=None, debug=False):
        winepath = self["ww_wine"] or self["default_winepath"]
        self._fixes_initialize(command)
        popen = self.run((winepath,)+command, env, debug)
        GLib.timeout_add(500, functools.partial(self._fixes_watch, popen))
        return popen

    def run(self, command, env=None, debug=False):
        '''
        Run any command in prefix environment.
        '''
        logging.debug("Run: %s" % repr(command))
        env = os.environ.copy() if env is None else env.copy()
        if "WINEDLLOVERRIDES" in env:
            dlloverrides = env["WINEDLLOVERRIDES"].split(";")
        else:
            dlloverrides = []
        dlloverrides.append(
            "winemenubuilder.exe=%s" % (
                "d" if self.winemenubuilder_disable else "n"))
        env.update({
            "WINEARCH": self.arch,
            "WINEDEBUG": "+all" if debug else "-all",
            "WINEDLLOVERRIDES": ";".join(dlloverrides),
            "WINEPREFIX": self.path,
            "WINESERVER": self["ww_wineserver"] or self["default_wineserverpath"],
            "WINELOADER": self["ww_wine"] or self["default_winepath"]
            })
        return subprocess.Popen(command, env = env)

    def _initial_save(self):
        '''
        Wait until directory is created and write unsaved config.
        '''
        if os.path.isdir(self._path):
            # Write unsaved data
            if self._unsaved:
                self._write(self._unsaved)
            return False
        return True

    def _symlink_save(self, destiny):
        '''
        Wait until directory is created and then symlink in wineprefixes and
        write unsaved config.
        '''
        if os.path.isdir(self._path):
            # Symlink to wineprefixes directory
            os.symlink(self._path, destiny)
            self._path = destiny
            # Write unsaved data
            if self._unsaved:
                self._write(self._unsaved)
            return False
        return True

    def save(self, env=None):
        '''
        Saves current prefix in bottlespec's wineprefixes directory
        '''
        newdir = os.path.expandvars("$HOME/.local/share/wineprefixes")
        deferred_action = None
        # Internal prefix
        if self._path.startswith(newdir):
            # Must be created
            if not os.path.exists(self._path):
                self.wine(("wineboot", "-i")) # WINE BUG WORKAROUND
                deferred_action = self._initial_save
        # External prefix (aka symlink prefix)
        else:
            # Link name
            new_path = alternative_if_exists(
                os.path.join(newdir, os.path.basename(self._path))
                )
            # Must be created
            if not os.path.exists(self._path):
                self.wine(("wineboot", "-i")) # WINE BUG WORKAROUND
                deferred_action = functools.partial(self._symlink_save, new_path)
            else:
                self._symlink_save(new_path)
        # Monitoring actions
        if deferred_action:
            if GLib.main_depth() == 0: # Outside mainloop
                while deferred_action():
                    time.sleep(0.2)
            else:
                GLib.timeout_add(200, deferred_action)

    def remove(self):
        '''
        prefix_path = os.path.expandvars(PREFIX_PATH)
        if self._path.startswith(prefix_path):
            if os.path.islink(self._path):
                rm(self.path)
            else:
                self.ignore = True

        me = abspath(self.path)
        for prefix in listdir(prefix_path):
            if me == abspath(prefix_path, ):
        '''
        pass

    @classmethod
    def iter_all(self, defaults, cb=None):
        newdir = os.path.expandvars(PREFIX_PATH)

        if not os.path.isdir(newdir):
            os.makedirs(newdir)

        # TODO(spayder26): remove some day in the future
        legacy_to_bottlespec(defaults)

        # TODO(spayder26): better ignore behavior
        # Bottlespec based prefixes
        for i in listdir(newdir):
            apath = os.path.abspath(os.path.join(newdir, i))
            rpath = os.path.realpath(os.path.join(newdir, i))
            # Must exists
            if os.path.isdir(rpath):
                prefix = Prefix(apath, defaults)
                if prefix["ww_ignore"]:
                    continue
                yield prefix
            # Broken prefix if doesn't and is link,
            elif os.path.islink(apath):
                yield BrokenPrefix(apath, defaults, cb)


class BrokenPrefix(Prefix):
    _icon = Gtk.STOCK_NO
    def __setitem__(self, x, y):
        pass

    def __getitem__(self, x):
        return self._defaults[x]

WINE_TOOLS = {
    "winetricks": (
        ("wine-winetricks", "winetricks", "wine"),
        ("winetricks",),
        ("winetricks",)),
    "winecfg":(
        ("wine-winecfg", "winecfg", "wine-cfg", "wine"),
        ("%(winepath)s",),
        ("%(winepath)s", "winecfg",)),
    "cmd":(
        ("terminal", "utilities-terminal", "bash", "gnome-eterm", "gnome-term",
         "gnome-terminal", "gnome-xterm", "Terminal", "xfce-terminal",
         "konsole", "lxterminal", "openterm", "Etermutilities-terminal"),
        ("%(winepath)s",),
        ("%(winepath)s", "wineconsole", "cmd")),
    "uninstaller":(
        ("wine-uninstaller", "wine"),
        ("%(winepath)s",),
        ("%(winepath)s", "uninstaller")),
    "explorer":(
        ("wine-explorer", "wine",),
        ("%(winepath)s",),
        ("%(winepath)s", "explorer")),
    "regedit":(
        ("wine-regedit", "wine"),
        ("%(winepath)s",),
        ("%(winepath)s", "regedit")),
    "browse folder":(
        ("gtk-directory",),
        ("xdg-open",),
        ("xdg-open", "%(prefix)s")),
    }

class Main(Gtk.Application):
    _current_prefix = None
    @property
    def current_prefix(self):
        return self._current_prefix

    @current_prefix.setter
    def current_prefix(self, v):
        if v != self._current_prefix:
            if v and v.callback is None:
                v.callback = self.action_prefix_changed
            self._current_prefix = v
            self.action_prefix_changed()

    @property
    def current_winepath(self):
        if self.current_prefix and self.current_prefix.winepath:
            return self.current_prefix.winepath
        return self.default_winepath

    LIST_PREFIX = 0
    LIST_PREFIX_BROKEN = 1
    LIST_SEPARATOR = 4
    LIST_NEW = 5
    LIST_ADD = 6

    def __getitem__(self, x):
        '''
        Shorthand for GtkBuilder's get_object.
        '''
        return self.gui.get_object(x)

    def __init__(self, args=None):
        Gtk.Application.__init__(self, application_id="apps.s26.pywinery")
        self.connect("activate", self.handle_activate)

        if args == None:
            args = [__file__]

        guifile = "/usr/share/pywinery/gui.glade"
        localgui = os.path.join(os.path.dirname(args[0]),"gui.glade")
        if os.path.isfile(localgui):
            guifile = localgui

        self.gui = None
        self.gui_file = guifile
        self.icon_extractor = ExeIconExtractor()

        self.default_winepath = getBin("wine")
        self.default_wineserverpath = getBin("wineserver")

        self.default_prefix_config = {
            "default_winepath": self.default_winepath,
            "default_wineserverpath": self.default_wineserverpath,
            "ww_name": None,
            "ww_known_executables" : "",
            "ww_wine": None,
            "ww_wineserver": None,
            "ww_winemenubuilder_disable" : None,
            "ww_ignore" : None,
            "ww_arch": "win32"
            }
        self.prefixes = list(Prefix.iter_all(self.default_prefix_config))
        self.prefixes_by_path = dict((i.path, i) for i in self.prefixes)

        self.default_environment = environ.copy()
        self.default_arch = None
        if self.default_winepath:
            self.default_arch = elfarch(self.default_winepath)

        self.given_msi = None
        self.given_cmd = None
        self.given_exe = None # absolute, not real

        self.flag_mode_debug = False
        self.flag_mode_nogui = False

        self.flag_remember = False
        self.flag_unknown_prefix = False
        self.flag_config_mode = False

        self.flag_treeview_click_time = 0

        c = 1
        for i in args[1:]:
            if i[0] != "-": break # Given command could contains - and --
            elif i == "-x" or i == "--nogui": self.flag_mode_nogui = True
            elif i == "-d" or i == "--debug": self.flag_mode_debug = True
            c += 1

        if self.flag_mode_debug:
            logging.getLogger().setLevel(logging.DEBUG)

        # Arg given after option params, assuming executable
        if len(args) > c:
            apath = args[c]
            if "://" in apath[3:10]:
                apath = GLib.filename_from_uri(apath, None)
            apath = os.path.abspath(apath)
            if os.path.isfile(apath): # Given arg is file, thus is exe or msi
                if Gio.content_type_guess(apath, None)[0].lower() == "application/x-msi":
                    self.given_msi = (apath,)+tuple(args[c+1:])
                else:
                    self.given_exe = (apath,)+tuple(args[c+1:])
                    for i in self.prefixes:
                        if apath in i.known_executables:
                            self.current_prefix = i
                            self.flag_remember = True
                            break

                if not self.current_prefix:
                    # Known prefix search on directory hierarchy
                    for i in self.prefixes:
                        if apath.startswith(i.path) or (
                          i.imported and
                          os.path.abspath(apath).startswith(os.path.realpath(i.path))
                          ):
                            self.current_prefix = i
                            break
                    else:
                        # New prefix search on directory hierarchy
                        sp = apath.split(os.sep)[:-1]
                        while len(sp) > 1:
                            lookdir = os.sep.join(sp)
                            lookdir_content = os.listdir(lookdir)
                            if (
                              "system.reg" in lookdir_content and
                              "drive_c" in lookdir_content and
                              "dosdevices" in lookdir_content):
                                self.flag_unknown_prefix = True
                                self.current_prefix = Prefix(lookdir, self.default_prefix_config)
                                break
                            sp.pop()
            else:
                self.given_cmd = tuple(args[c:])
        self.flag_config_mode = not (self.given_msi or self.given_cmd or self.given_exe)

    def action_open_directory(self, directory):
        for i in ("xdg-open", "thunar", "pacman", "nautilus", "dolphin"):
            if checkBin(i):
                subprocess.Popen((i, directory), env=self.default_environment)
                break
        else:
            logging.error("Unable to find a file browser.")

    def action_launch(self):
        if self.given_msi:
            rpath = self.given_msi[0]
            command = ("msiexec", "/i") + self.given_msi
        elif self.given_exe:
            rpath = self.given_exe[0]
            command = self.given_exe
        else:
            rpath = None
            command = self.given_cmd

        if rpath:
            known = self.current_prefix.known_executables
            if self.flag_remember:
                if not rpath in known:
                    known.append(rpath)
            elif rpath in known:
                known.remove(rpath)
        self.current_prefix.wine(command, env=self.default_environment, debug=self.flag_mode_debug)

    def run(self):
        Gtk.Application.run(self, None)

    def aux_separator_func(self, model, row, data=None):
        return model.get_value(row, 4) == self.LIST_SEPARATOR

    def handle_activate(self, widget):
        '''
        Called once application is activated (Gtk3 way)
        '''
        if self.flag_mode_nogui:
            if self.given_msi or self.given_exe or self.given_cmd:
                if self.current_prefix:
                    if self.flag_unknown_prefix:
                        stderr.write("Autodetected unknown prefix.%s" % linesep)
                    self.action_launch()
                else:
                    sys.stderr.write("Pywinery is unable to find a suitable prefix.%s" % linesep)
            else:
                sys.stderr.write("Nothing to do.%s" % linesep)
            sys.exit(1)
        else:
            self.guiStart()

    # TODO
    def handler_error(self, code=None, message=None):
        if code == None:
            self.xml.get_widget("errorbox").set_property("visible", False)
        else:
            self.xml.get_widget("labelerror").set_label(message)
            self.xml.get_widget("errorbox").set_property("visible", True)

    def handle_button_run(self, widget):
        self.action_launch()
        self.quit()

    def handle_iconview_item_activated(self, widget, path):
        iiiid = widget.get_model()[path][3] # internal iconview item id

        if widget == self["iconview1"]:
            exec_variables = {
                "prefix": self.current_prefix.path,
                "winepath": self.current_winepath
                }
            self.current_prefix.run(
                [i % exec_variables for i in WINE_TOOLS[iiiid][2]],
                env=self.default_environment, debug=self.flag_mode_debug
                )
        else:
            self.current_prefix.wine(
                (iiiid,), # internal id for iconview2 is executable path
                env=self.default_environment, debug=self.flag_mode_debug
                )

    def aux_dialog_prefix_name(self, name="", arch=None, new=False, transient=None):
        '''
        Show prefix name dialog

        Args:
            name: str, default name.
                  Default: ""
            arch: str, architecture (win32 or win64) or None if not available.
                  Default: False.
            new:  bool, show ADD button instead of OK button.
                  Default: False

        Returns:
            Tuple as (name, arch) or (None, None) on user cancel.
        '''
        dialog2 = self["dialog_new"]
        dialog2.set_transient_for(self["dialog_main"] if transient is None else transient)
        self["button10"].set_property("visible", True) # add button
        self["button8"].set_property("visible", False) # ok button
        self["combobox2"].set_property("visible", not arch is None) # arch combo
        archmodel = self["combobox2"].get_model()
        if arch:
            # Default arch combo value
            for n, (m,) in enumerate(archmodel):
                if m == arch:
                    self["combobox2"].set_active(n)
                    break
            else:
                self["combobox2"].set_active(0)
        while True:
            # Repeat until cancel or valid name
            self["entry2"].set_text(name)
            response = dialog2.run()
            dialog2.hide()
            if response == 1:
                name = self["entry2"].get_text().strip()
                if name:
                    if arch is None:
                        return (name, None)
                    return (name, archmodel[self["combobox2"].get_active()][0])
            else:
                break
        return (None, None)

    def handle_add_known_executable(self, widget):
        filefilter = Gtk.FileFilter()
        filefilter.set_name("Windows executable")
        filefilter.add_pattern("*.exe")
        filefilter.add_pattern("*.bat")
        filefilter.add_pattern("*.com")
        dialog1 = Gtk.FileChooserDialog(
            _("Choose a windows executable"),
            self["dialog_config"],
            Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_ADD, Gtk.ResponseType.OK))
        dialog1.add_filter(filefilter)
        dialog1.set_local_only(True)
        while True:
            response = dialog1.run()
            dialog1.hide()
            if response == Gtk.ResponseType.OK:
                filenames = [i for i in dialog1.get_filenames() if os.path.isfile(i)]
                self.current_prefix.known_executables.extend(filenames)
                break
            else:
                break
        dialog1.destroy()

    def handle_iconview_keypress(self, widget, event):
        if event.keyval == Gdk.KEY_Delete:
            model = self["iconview2"].get_model()
            for row in self["iconview2"].get_selected_items():
                self.current_prefix.known_executables.remove(model[row][3])

    def handle_treeview_keypress(self, widget, event):
        if event.keyval == Gdk.KEY_Delete:
            selection = widget.get_selection()
            # Prefix removal
            model, paths = selection.get_selected_rows()
            blacklist = []
            for path in paths:
                prefix = self.prefixes_by_path.pop(model[path][0])
                self.prefixes.remove(prefix)
                move_to_trash(prefix.path)
                blacklist.append(model[path].iter)
            # Other row selection
            for row in model:
                if row[0] and not row.iter in blacklist:
                    self.current_prefix = self.prefixes_by_path[row[0]]
                    break
            else:
                self.current_prefix = None
            self.guiPrefix()

    def handle_remember(self, *args):
        self.flag_remember = self["checkbutton1"].get_property("active")

    def handle_set_winepath(self, widget):
        winepath = widget.get_filename()
        if winepath:
            self.current_prefix.winepath = winepath

    def handle_reset_winepath(self, widget):
        self.current_prefix.winepath = None
        self["filechooserbutton1"].set_filename(self.default_winepath)

    def handle_set_wineserverpath(self, widget):
        wineserverpath = widget.get_filename()
        if wineserverpath:
            self.current_prefix.wineserverpath = wineserverpath

    def handle_reset_wineserverpath(self, widget):
        self.current_prefix.wineserverpath = None
        self["filechooserbutton2"].set_filename(self.default_wineserverpath)

    def handle_winemenubuilder_toggled(self, widget):
        self.current_prefix.winemenubuilder_disable = widget.get_property("active")

    _combo_internal_change = False
    def aux_handler_combo(self, row, dialog, allow_internals=True):
        '''

        Args:
            row: Prefixes' model row
            dialog: Parent dialog will be parent of new ones

        Returns:
            True if internally managed or False if prefix.

        '''
        internal = True
        new_prefix = None
        action = row[4]
        if action == self.LIST_PREFIX or action == self.LIST_PREFIX_BROKEN:
            path = row[0]
            self.current_prefix = self.prefixes_by_path[path]
            internal = False
        elif allow_internals and action == self.LIST_NEW:
            name, arch = self.aux_dialog_prefix_name(
                arch=self.default_arch,
                new=True,
                transient=dialog
                )
            if name:
                prefix = Prefix(
                    alternative_if_exists("$HOME/.local/share/wineprefixes/%s" % name),
                    self.default_prefix_config
                    )
                prefix.name = name # Must be setted before save
                prefix.arch = arch
                new_prefix = prefix
        elif allow_internals and action == self.LIST_ADD:
            dialog1 = Gtk.FileChooserDialog(
                _("Select prefix directory"),
                self["dialog_main"],
                Gtk.FileChooserAction.SELECT_FOLDER,
                (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_ADD, Gtk.ResponseType.OK))
            dialog1.set_local_only(True)
            while True:
                response = dialog1.run()
                dialog1.hide()
                if response == Gtk.ResponseType.OK:
                    filename = dialog1.get_filename()
                    prefix = Prefix(
                        os.path.abspath(filename),
                        self.default_prefix_config
                        )
                    name, arch = self.aux_dialog_prefix_name(
                        prefix.name,
                        None if os.path.exists(prefix.path) else prefix.arch,
                        new=True,
                        transient=dialog
                        )
                    if name:
                        prefix.name = name
                        prefix.ignore = None
                        prefix.arch = arch
                        new_prefix = prefix
                    break
                else:
                    break
            dialog1.destroy()
        if new_prefix:
            new_prefix.save(env=self.default_environment)
            if not new_prefix in self.prefixes:
                self.prefixes_by_path[prefix.path] = new_prefix
                self.prefixes.append(new_prefix)
            self.guiPrefix()
            self.current_prefix = new_prefix
        return internal

    def action_prefix_changed(self, prefix=None):
        if prefix is None:
            prefix = self.current_prefix
        if prefix is None:
            # No hay prefijo seleccionado
            self["notebook1"].set_property("sensitive", False)
            self._treeview_last_index = -1
            self._treeview_last = None
        elif prefix == self.current_prefix and self.gui:
            self["notebook1"].set_property("sensitive", True)
            prefixpos = -1
            # Prefix selection
            for n, row in enumerate(self["prefixstore"]):
                if row[0] == self.current_prefix.path:
                    prefixpos = n
                    break

            # Model update
            if prefixpos > -1:
                row = self["prefixstore"][prefixpos]
                row[1] = prefix.icon

                # Realtime name (and alias) update
                if row[2] != prefix.name:
                    old_name = row[2]
                    row[2] = prefix.name
                    # Look for name collisions
                    old_name_collisions = 0
                    new_name_collisions = 0
                    for n, orow in enumerate(self["prefixstore"]):
                        if orow[0] and n != prefixpos:
                            if orow[2] == prefix.name :
                                orow[3] = os.path.basename(orow[0])
                                new_name_collisions += 1
                            elif orow[2] == old_name:
                                old_name_collisions += 1
                    # Any new name collision, adding basename
                    if new_name_collisions:
                        row[3] = os.path.basename(row[0])
                    else:
                        row[3] = ""
                    # Only one old name collision, remove its basename
                    if old_name_collisions == 1:
                        for orow in self["prefixstore"]:
                            if orow[0] and orow[2] == old_name:
                                orow[3] = ""
                                break

            # Prefix property handling for main dialog
            if self["dialog_main"].get_property("visible"):
                self["combobox1"].set_active(prefixpos)

                # Prefix is active
                self["button1"].set_property("sensitive", not prefix is None and prefix.ready)

                # Winepath check
                runable = False
                if prefix and prefix.ready:
                    runable = (
                        checkBin(prefix.winepath or self.default_winepath)
                        and not isinstance(prefix, BrokenPrefix)
                        )
                self["button3"].set_property("sensitive", runable)

                # Remember
                given = (self.given_msi or self.given_exe)
                if given:
                    remember = given[0] in prefix.known_executables
                    if remember != self["checkbutton1"].get_property("active"):
                        self["checkbutton1"].set_property("active", remember)
            # Prefix property asignment for config dialog
            if self["dialog_config"].get_property("visible") and prefixpos > -1:
                self["scrolledwindow1"].set_property("sensitive", prefix and prefix.ready)

                self["treeview1"].set_cursor((prefixpos,))

                # These changes emit signals, we have to check changes first
                if self["entry1"].get_text() != prefix.name:
                    self["entry1"].set_text(prefix.name)

                if self["label8"].get_label() != prefix.arch:
                    self["label8"].set_label(prefix.arch)

                if self["checkbutton2"].get_property("active") != prefix.winemenubuilder_disable:
                    self["checkbutton2"].set_property("active", prefix.winemenubuilder_disable)

                winepath = self.current_prefix.winepath or self.default_winepath
                if winepath != self["filechooserbutton1"].get_filename():
                    self["filechooserbutton1"].set_filename(winepath)

                wineserverpath = self.current_prefix.wineserverpath or self.default_wineserverpath
                if wineserverpath != self["filechooserbutton1"].get_filename():
                    self["filechooserbutton2"].set_filename(wineserverpath)
                self.action_gui_executables()


    _combo_last = -1
    def handle_combo_change(self, widget, user_data=None):
        if self._model_work:
            return
        active = self["combobox1"].get_active()
        if active != self._combo_last:
            internal = True
            if active > -1:
                internal = self.aux_handler_combo(
                    self["prefixstore"][active],
                    self["dialog_main"])
            if internal:
                self["combobox1"].set_active(self._combo_last)
            else:
                self._combo_last = active

    _treeview_last_index = -2
    _treeview_last = None
    def handle_treeview_change(self, widget, user_data=None):
        if self._model_work:
            return
        selection = widget.get_selection()
        model, paths = selection.get_selected_rows()
        if not paths:
            return
        #path, column = widget.get_cursor()
        path = paths[0]
        indices = path.get_indices() if path else None
        if indices and indices[0] != self._treeview_last_index:
            internal = True
            if path:
                internal = self.aux_handler_combo(
                    self["prefixstore"][path],
                    self["dialog_config"],
                    self._treeview_last_index != -2)
            if internal:
                if self._treeview_last is None:
                    self._treeview_last_index = -1
                    self["treeview1"].get_selection().unselect_all()
                else:
                    self["treeview1"].set_cursor(self._treeview_last)
            else:
                self._treeview_last = path
                self._treeview_last_index = indices[0]

    def handle_button_close(self, widget):
        self.quit()

    def handle_main_destroy(self, widget):
        self.quit()

    def handle_config_response(self, widget, response):
        if self.flag_config_mode:
            self.quit()

    def _app_quit(self):
        for prefix in self.prefixes:
            if prefix.running_commands > 0:
                return True
        Gtk.Application.quit(self)
        return False

    def quit(self):
        self["dialog_main"].hide()
        self["dialog_config"].hide()
        GLib.idle_add(self._app_quit)

    def handle_delete(self, widget, *args):
        '''
        Handle and stop delete event, just hide.
        '''
        widget.set_property("visible", False)
        return True

    def guiStart(self):

        self.gui = Gtk.Builder()
        self.gui.set_translation_domain(locale_domain)
        self.gui.add_from_file(self.gui_file)
        self.gui.connect_signals(self)

        show = ()
        if self.given_msi or self.given_exe:
            show = ("button3", "button5", "checkbutton1") # Launch, cancel, remember
        elif self.given_cmd:
            show = ("button3", "button5") # Launch, cancel
        else: # Nothing given (configmode)
            show = ("button4",) # Close

        for i in show:
            self[i].set_property("visible", True)

        self["label5"].set_property("max-width-chars", len(self["label2"].get_property("label"))-2)

        self["combobox1"].set_row_separator_func(self.aux_separator_func, None)
        self["treeview1"].set_row_separator_func(self.aux_separator_func, None)

        if self.flag_unknown_prefix:
            response = self["dialog_remember"].run()
            if response == 1:
                # Register prefix
                prefix = self.current_prefix
                prefix.save()
                self.prefixes.append(prefix)
                self.prefixes_by_path[prefix.path] = prefix
            else:
                # Forget current prefix
                self.current_prefix = None

        self.guiPrefix()

        if self.flag_config_mode:
            if self.prefixes:
                self["treeview1"].set_cursor((0,))
            self["dialog_config"].set_property("skip-taskbar-hint", False)
            self.add_window(self["dialog_config"])
            self["dialog_config"].set_property("visible", True)
            self["dialog_config"].set_icon_name("pywinery")
        else:
            self["scrolledwindow2"].set_property("visible", False)
            self.add_window(self["dialog_main"])
            self["dialog_main"].set_property("visible", True)
            self["dialog_config"].set_icon_name("gtk-preferences")

        # Selecting current prefix
        self.action_prefix_changed()

    def handle_entry_name_change(self, widget):
        name = widget.get_text()
        self.current_prefix.name = name

    def handle_button_show_config(self, widget):
        self["dialog_config"].show()
        self.action_prefix_changed()

    def handle_button_hide_config(self, widget):
        self["dialog_config"].hide()

    def handle_iconview_selection_changed(self, widget):
        iconview = self["iconview2" if widget == self["iconview1"] else "iconview1"]
        if iconview.get_selected_items() and widget.get_selected_items():
            iconview.unselect_all()

    _update_iconviews = False
    def handle_iconview_draw(self, widget, cairo_context):
        '''
        Calculate and set the best item-width for both iconviews
        Should be called once iconview items were drawed.
        '''

        if self._update_iconviews:
            # Run only when requested and until all iconviews are drawed
            item_widths = [
                self[iconview].get_cell_rect(row.path, None)[1].width
                for iconview in ("iconview1", "iconview2")
                    for row in self[iconview].get_model()]
            if not -1 in item_widths:
                item_width = max(item_widths)
                self._update_iconviews = False
                for view in ("iconview1", "iconview2"):
                    self[view].set_property("item-width", item_width)

    def action_set_exe_icons(self, icon_size):
        model = self["iconstore2"]
        for path, row in zip(self.current_prefix.known_executables, model):
            row[0] = self.icon_extractor.extract(path, icon_size)

    def action_gui_executables(self):
        '''
        Updates de executable model based on available wine tools and known
        prefix executables.
        '''
        icon_size = 32
        theme = Gtk.IconTheme.get_default()


        # Glade bug workaround
        self["cellrenderertext1"].set_property("xalign", 0.5)
        self["cellrenderertext6"].set_property("xalign", 0.5)

        missing_icon = theme.load_icon("gtk-missing-image", icon_size, 0)
        error_icon = theme.load_icon("gtk-missing-image", icon_size, 0)

        exec_variables = {
            "prefix": self.current_prefix.path,
            "winepath": self.current_winepath
            }

        model = self["iconstore1"]
        model.clear()
        for text, (icon_names, requirements, command) in WINE_TOOLS.iteritems():
            available = all(checkBin(i % exec_variables) for i in requirements)
            icon = missing_icon
            if available:
                for icon_name in icon_names:
                    try:
                        if theme.has_icon(icon_name):
                            icon = theme.load_icon(icon_name, icon_size, 0)
                            break
                    except BaseException as e:
                        # Bug in GTK
                        logging.exception(e)
            model.append((icon, text, available, text))

        known_executables = self.current_prefix.known_executables

        model = self["iconstore2"]
        model.clear()
        for path in known_executables:
            icon = missing_icon
            available = os.path.exists(path)
            icon = self.icon_extractor.get_from_cache(path, icon_size)
            model.append((icon, os.path.basename(path), available, path))

        show_executables = bool(known_executables)
        if show_executables:
            GLib.idle_add(self.action_set_exe_icons, icon_size)
            self._update_iconviews = True
        else:
            self["iconview1"].set_property("item-width", -1)

        self["iconview1"].set_property("expand", not show_executables)
        self["label10"].set_label(_("Known executables") if show_executables else _("No known executables"))
        self["iconview2"].set_property("visible", show_executables)

    _model_work = False
    def guiPrefix(self):
        '''
        Updates the prefix model based on self.prefixes value.

        Initializes combobox.
        '''
        self._model_work = True
        # Combobox initialization
        model = self["prefixstore"]
        model.clear()

        names = [prefix.name for prefix in self.prefixes]
        for prefix in sorted(self.prefixes, cmp=lambda x, y: locale.strcoll(x.name, y.name)):
            # Second name (path ending) if conflict
            alias2 = None
            if names.count(prefix.name) > 1:
                alias2 = "%s" % os.path.basename(prefix.path)
            ptype = self.LIST_PREFIX
            if isinstance(prefix, BrokenPrefix):
                ptype = self.LIST_PREFIX_BROKEN
            model.append((prefix.path, prefix.icon, prefix.name, alias2, ptype))

        # Adding actions
        if self.prefixes: # Separator
            model.append((None, None, None, None, self.LIST_SEPARATOR))

        model.append((None, Gtk.STOCK_ADD, _("Add existing prefix"), None, self.LIST_ADD))
        model.append((None, Gtk.STOCK_NEW, _("Create new prefix"), None, self.LIST_NEW))
        self._model_work = False

if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = sys.argv[0]

    if "--help" in args or "-h" in args:
        print('''%(cmd)s - easy graphical tool for wineprefixing.
Usage:
    %(cmd)s [OPTIONS...] COMMAND [ARGUMENTS...]

Options:
    -v, --version     Prints Wine and Pywinery's version.
    -x, --nogui       Run with autodetected prefix if possible.
    -d, --debug       Show's wine debug messages.
    -h, --help        Show this help.
''' % locals())
    elif "--version" in args or "-v" in args:
        print("%s-%s; %s" % (
            cmd,
            ".".join(str(i) for i in __version__),
            wineVersion() or "wine not found in PATH.")
            )
    else:
        if "-p" in args:
            logging.getLogger().setLevel(logging.DEBUG)
        app = Main(sys.argv)
        app.run()
