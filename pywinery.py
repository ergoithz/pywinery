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
__version__ = (0, 2, 0)
__author__ = "Felipe A. Hernandez <spayder26@gmail.com>"

from sys import exit as sys_exit, argv as sys_argv, stderr
try:
    import pygtk
    pygtk.require("2.0")
except:
    pass
try:
    import gtk
    import pango
    import gtk.glade
    import gobject
    import atk
except:
    sys_exit(1)

from os.path import realpath, abspath, split as path_split, join as path_join,\
    isfile, isdir, islink, isabs, expandvars, dirname, exists
from os import environ, listdir, sep, linesep, kill  as os_kill, getuid,\
    getgid, remove, mkdir, symlink, access, X_OK

from commands import getoutput
from subprocess import Popen
from mimetypes import guess_type
from threading import Thread
from time import sleep, time
from exceptions import ValueError

from shutil import rmtree

def mkpath(path):
    path = path.split(sep)
    unfinished = ""
    for i in path:
        unfinished += "%s%s" % (i, sep)
        if not isdir(unfinished):
            mkdir(unfinished)
            
def relativize(path, prefix):
    path = abspath(path)
    home = environ["HOME"]
    if home[-1] == sep: home = home[:-1]
    for old, new in ((prefix.path, ""), (realpath(prefix.path), ""), (home, "$HOME")):
        if path.startswith(old): return "%s%s%s" % (new, sep if new else "", path[len(old)+1:])
    return path
    
def unrelativize(path, prefix):
    path = expandvars(path)
    if isabs(path): return path
    return path_join(prefix.path, path)
    
def getPrefixes(defaults):
    configdir = expandvars("$HOME/.config/pywinery")
    newdir = expandvars("$HOME/.local/share/wineprefixes")
    old =  path_join(configdir, "prefixes.config")
    if not isdir(newdir): mkpath(newdir)
    #if not isdir(configdir): mkpath(configdir)
    if isfile(old):
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
            rpath = realpath(path_join(newdir, i))
            for j in configlines.keys():
                if realpath(j) == rpath:
                    prefix = Prefix(rpath, defaults)
                    prefix.extend_known_executables(configlines[j])
                    del configlines[j]
                
        # Newdir prefix linking   
        for key, values in configlines.iteritems():
            if isdir(key): # We cannot import broken prefixes
                end = key.split(sep)[-1]                
                prefix = Prefix(key, defaults)
                prefix["ww_name"] = end
                prefix.extend_known_executables(configlines[j])
                prefix.memorize()
        remove(old)

    #TODO: ignore behavior
    tr = []
    for i in listdir(newdir):
        apath = abspath(path_join(newdir, i))
        rpath = realpath(path_join(newdir, i))
        if isdir(rpath):
            prefix = Prefix(apath, defaults)
            if prefix["ww_ignore"]: continue
            tr.append(prefix)
        else: tr.append(BrokenPrefix(apath, defaults))
    return tr

def namer(path):
    ''' Receives a path and returns an alternative if alredy exists '''
    temptative = path
    counter = 1
    while exists(temptative):
        counter += 1
        temptative = "%s_%d" % (path, counter)
    return temptative

# Enviroment's detection and actions
def getBin(name):
    return getoutput("which %s" % name).strip() or None

def checkBin(name):
    if exists(name) and access(name, X_OK): return True
    return bool(getBin(name))

def killPopen(p, signal=15):
    if hasattr(p, "send_signal"):
        p.send_signal(signal)
    else:
        # For python < 2.6
        os_kill(p.pid, signal)
        
def toolModel( winepath = "wine", wineprefix = "",  model = None ):
    '''
    Returns a model of found  prefix-related tools using the following row
    format:
        ( icon_pixbuf, icon_text, GTuple( executable_path, *arguments ))
    '''
    # tools format:
    #   text : (list of options...)
    # option format:
    #   (icon_name, required_binaries, command, WTF)    
    tools = { 
        "Winetricks":(
            ("wine-winetricks", ("winetricks",), ("winetricks",)),),
        "Winecfg":(
            ("wine-winecfg", (winepath,), (winepath, "winecfg",)),),
        "Wine cmd":(
            ("terminal", ("x-terminal-emulator", winepath,), (
                "x-terminal-emulator","-e", winepath, "cmd")),
            ("terminal", ("xterm", winepath,), (
                "xterm","-e", winepath, "cmd")),
            ),
        "Wine uninstaller":(
            ("wine-uninstaller", (winepath,), (winepath, "uninstaller")),),
        "Wine explorer":(
            ("wine", (winepath,), (winepath, "explorer")),),
        "Wine regedit":(
            ("wine", (winepath,), (winepath, "regedit")),),
        "Browse prefix folder":(
            ("gtk-directory", ("xdg-open",), ("xdg-open","%s" % wineprefix)),),
        }
    theme = gtk.icon_theme_get_default()
    if model is None: model = gtk.ListStore(gtk.gdk.Pixbuf, str, GTuple)
    for text in tools:
        for icon_name, requirements, command in tools[text]:
            valid_option = True
            for i in requirements:
                if not checkBin(i):
                    valid_option = False
                    break
            if valid_option:
                icon = "gtk-missing-image"
                try:
                    if theme.has_icon(icon_name): icon = icon_name
                except: pass
                model.append((
                    theme.load_icon(icon, 24, 0),
                    text,
                    GTuple((getBin(command[0]),)+command[1:])))
                break
    return model

class LoopHalt(Exception):
    def __str__(self):
        return "Loop halted"

class GTuple(gobject.GObject):
    '''
    Custom gobject type to store any value.
    Used getTools to return a gtk.TreeModel compatible model.
    '''
    tup = None
    def __init__(self, tup):
        gobject.GObject.__init__(self)
        self.tup = tup
    
class BrokenPrefix(object):
    def __init__(self, path, defaults):
        self.winepath = None
        self.path = path
        self.defaults = defaults
        self.known_executables = ()
        self.imported = True # Only imported prefixes can be broken
        
    def knows_executable(self, x):
        return False
        
    def add_known_executable(self, x):
        pass
        
    def remove_known_executable(self, x):
        pass
        
    def extend_known_executables(self, x):
        pass
        
    def __setitem__(self, x, y):
        pass
        
    def __getitem__(self, x):
        return self.defaults[x]


class Prefix(object):
    @property
    def path(self): return self._path
    
    @property
    def winepath(self):
        tr = self["ww_wine"]
        if tr: return unrelativize(tr, self)
        return tr
        
    @winepath.setter
    def winepath(self, x):
        if x: self["ww_wine"] = relativize(x, self)
        else: self["ww_wine"] = self._defaults["ww_wine"]
    
    @property
    def known_executables(self):
        if self["ww_known_executables"]:
            return tuple(unrelativize(i, self) for i in self["ww_known_executables"].split(":"))
        return ()
        
    def add_known_executable(self, x):
        x = relativize(x, self)
        known = self["ww_known_executables"]
        if known: 
            known = known.split(":")
            if x not in known:
                known.append(x)
                self["ww_known_executables"] = ":".join(known)
        else:
            self["ww_known_executables"] = x
        
    def remove_known_executable(self, x):
        known = self["ww_known_executables"]
        if known:
            known = known.split(":")
            x = relativize(x, self)
            if x in known:
                known.remove(x)
                self["ww_known_executables"] = ":".join(known)
        
    def extend_known_executables(self, x):
        known = self["ww_known_executables"]
        if known: known = known.split(":")
        else: known = []
        nold = len(known)
        for i in x:
            i = relativize(i, self)
            if i not in known: known.append(i)
        if len(known) != nold: self["ww_known_executables"] = ":".join(known)
        
    @property
    def imported(self):
        return islink(self._path)

    def __init__(self, path, defaults):
        if not isabs(path):
            path = expandvars("$HOME/.local/share/wineprefixes/%s" % path)
        self._path = path
        self._config = path_join(path, "wrapper.cfg")
        self._defaults = defaults
        self._cache = {}
    
    def __setitem__(self, x, y):
        found = False
        del_item = False
        if x in self._defaults and y == self._defaults[x]:
            if x in self._cache: del self._cache[x]
            del_item = True
        else: self._cache[x] = y
        if isfile(self._config):
            f = open(self._config, "r")
            data = f.readlines()
            newlinechar = linesep
            if not f.newlines is None:
                if f.newlines is tuple:
                    newlinechar = f.newlines[-1]
                else:
                    newlinechar = f.newlines
            f.close()
            
            for i in xrange(len(data)):
                if data[i].split("=")[0] == x:
                    if del_item: data[i] = ""
                    else: data[i] = "%s=\"%s\"%s" % (x, y, newlinechar)
                    found = True
                    break
        else:
            newlinechar = linesep
            data = []
        if not found and not del_item: data.append("%s=\"%s\"%s" % (x, y, newlinechar))
        f = open(self._config, "w")
        f.writelines(data)
        f.close()
        
    def __getitem__(self, x):
        if x in self._cache: return self._cache[x]
        elif isfile(self._config):
            f = open(self._config, "r")
            data = f.readlines()
            newlinechar = linesep
            if not f.newlines is None:
                if f.newlines is tuple: newlinechar = f.newlines[-1]
                else: newlinechar = f.newlines
            f.close()
            for i in xrange(len(data)): # We cache all data
                if "=" in data[i] and data[i].strip()[0] != "#":
                    key, value = data[i].split("=")
                    key = key.strip()
                    value = value.strip()
                    if value[0] == "\"": value = value[1:-1]
                    #if key in self._defaults and value != self._defaults[key]:
                    self._cache[key] = value
            if x in self._cache: return self._cache[x]
        if x in self._defaults: return self._defaults[x]
        raise KeyError("No variable with name %s." % x)
        
    def memorize(self):
        newdir = expandvars("$HOME/.local/share/wineprefixes")
        if self._path.startswith(newdir): # internal prefix
            if not exists(self._path): mkdir(self._path)
        else: # external prefix, must symlink and change self._path
            if not exists(self._path): mkdir(self._path)
            # Symlink to wineprefixes directory
            
            # Generate symlink name
            old_path = self._path
            new_path = namer(path_join(newdir, path_split(self._path)[-1]))
    
            symlink(old_path, new_path)
            self._path = new_path            

class Main(object):            
    @classmethod
    def default_treeview_sort(self, model, iter1, iter2):
        a1 = model.get_value(iter1, 0)
        a2 = model.get_value(iter1, 4)
        b1 = model.get_value(iter2, 0)
        b2 = model.get_value(iter2, 4)
        if a2 and b2:
            return cmp(a1+a2,b1+b2) 
        return cmp(a1,b1)
        
    constant_treeview_prefix = 0
    constant_treeview_executable = 1
    constant_treeview_broken_prefix = 2
    constant_treeview_broken_executable = 3

    def __init__(self, args=None):
        if args == None: args = [__file__]
        guifile = "/usr/share/pywinery/gui.glade"
        localgui = path_join(dirname(args[0]),"gui.glade")
        if isfile(localgui): guifile = localgui

        self.killable_threads = []
        self.xml = gtk.glade.XML(guifile)
        
        self.default_prefix_config = {
            "ww_name": None,
            "ww_known_executables" : "",
            "ww_wine": None,
            "ww_winemenubuilder_disable" : None,
            "ww_ignore" : None
            }
        self.prefixes = getPrefixes(self.default_prefix_config)
        self.prefixes_by_id = dict((id(i), i) for i in self.prefixes)
        self.prefixes_by_path = dict((i.path, i) for i in self.prefixes)
        
        self.lastTreeviewClick = 0
        
        self.initialized_combo = False
        self.initialized_treeview = False

        self.default_winepath = getBin("wine")
        self.default_environment = environ.copy()
        
        self.given_msi = None
        self.given_cmd = None 
        self.given_exe = None # absolute, not real
        
        self.flag_mode_config = False
        self.flag_mode_debug = False
        self.flag_mode_nogui = False
        
        self.flag_remember = False
        self.flag_unknown_prefix = False
        
        self.flag_treeview_click_time = 0
        
        self.current_prefix = None

        c = 1
        for i in args[1:]:
            if i[0] != "-": break # Given commands can contains - and -- too
            elif i == "-x" or i == "--nogui": self.flag_mode_nogui = True
            elif i == "-d" or i == "--debug": self.flag_mode_debug = True
            elif i == "-c" or i == "--config": self.flag_mode_config = True
            c += 1

        if len(args) > c:
            apath = abspath(args[c])
            if isfile(apath): # Given arg is file, thus is exe or msi
                if guess_type(apath)[0].lower() == "application/x-msi":
                    self.given_msi = (apath,)+tuple(args[c+1:])
                else:
                    self.given_exe = (apath,)+tuple(args[c+1:])
                    for i in self.prefixes:
                        if relativize(apath, i) in i["ww_known_executables"].split(":"):
                            self.current_prefix = i
                            self.flag_remember = True
                            break

                if not self.current_prefix:
                    for i in self.prefixes:
                        if apath.startswith(i.path) or ( i.imported and
                          abspath(apath).startswith(realpath(i.path)) ):
                            self.current_prefix = i
                            break
                    else: # If given cmd isn't on any prefix
                        sp = apath.split(sep)[:-1]
                        while len(sp) > 1:
                            lookdir = sep.join(sp)
                            print lookdir
                            lookdir_content = listdir(lookdir)
                            if (
                              "system.reg" in lookdir_content and
                              "drive_c" in lookdir_content and
                              "dosdevices" in lookdir_content):
                                self.flag_unknown_prefix = True
                                self.current_prefix = Prefix(lookdir, self.default_prefix_config)
                                break
                            sp.pop()
            else:
                self.given_cmd = args[c:]
    
    def action_open_directory(self, directory):
        for i in ("xdg-open", ):
            if checkBin(i):
                Popen((i, directory), env=self.default_environment)
                break
        else:
            self.xml.get_widget("labelerror").set_label("Cannot open: exo-open nor xdg-open found.")
            self.xml.get_widget("errorbox").set_property("visible", True)
        
    def action_run_at_prefix(self, prefix, command):
        if self.flag_mode_debug: print("Pywinery: %s" % repr(command))
        if isinstance(prefix, int): prefix = self.prefixes_by_id[prefix]
        elif isinstance(prefix, basestring):  prefix = self.prefixes_by_path[prefix]
        env = self.default_environment.copy()
        if self.flag_mode_debug: env["WINEDEBUG"] = "+all"
        else: env["WINEDEBUG"] = "-all"
        if prefix["ww_winemenubuilder_disable"]: ov =  "winemenubuilder.exe=d"
        else: ov =  "winemenubuilder.exe=n"
        if "WINEDLLOVERRIDES" in env: env["WINEDLLOVERRIDES"] = "%s;%s" % (env["WINEDLLOVERRIDES"], ov)
        else: env["WINEDLLOVERRIDES"] = ov
        env["WINEPREFIX"] = prefix.path
        Popen(command, env = env)
        
    def run(self):
        if self.flag_mode_nogui:
            if self.given_msi or self.given_exe or self.given_cmd:
                if self.current_prefix:
                    if self.flag_unknown_prefix: stderr.write("Autodetected unknown prefix.")
                    self.handler_launch()
                else: stderr.write("Pywinery is unable to find a suitable prefix.%s" % linesep)
            else: stderr.write("Nothing to do.%s" % linesep)
            sys_exit(1)
        else:
            if self.flag_unknown_prefix:
                dialog = self.xml.get_widget("dialog1")
                if dialog.run() == 1:
                    self.prefixes.append(self.current_prefix)
                    self.current_prefix.memorize()
                dialog.hide()
            gtk.gdk.threads_init()
            self.guiStart()
            self.xml.get_widget("window1").set_property("visible", True)
            gtk.main()

    def initialize_combo(self):
        combo = self.xml.get_widget("combobox1")
        model = combo.get_model()
        if self.initialized_combo:
            model.clear()
            for i in model: model.remove(i.iter)
        else:
            model = gtk.ListStore(gobject.TYPE_INT, gtk.gdk.Pixbuf, gobject.TYPE_STRING, gobject.TYPE_STRING)
            model.set_sort_column_id(2, gtk.SORT_ASCENDING)
            combo.set_model(model)
            render = gtk.CellRendererPixbuf()
            #render.set_property("alignment", pango.ALIGN_RIGHT)
            combo.pack_start(render, False)
            combo.add_attribute(render, 'pixbuf', 1)
            
            render = gtk.CellRendererText()
            render.set_property("ellipsize-set", False)
            render.set_property("alignment", pango.ALIGN_LEFT)
            combo.pack_start(render, True)
            combo.add_attribute(render, 'text', 2)
            
            render = gtk.CellRendererText()
            render.set_property("ellipsize-set", pango.ELLIPSIZE_START)
            render.set_property("weight", 300)
            render.set_property("scale", 0.8)
            #render.set_property("alignment", pango.ALIGN_RIGHT)
            combo.pack_start(render, False)
            combo.add_attribute(render, 'text', 3)
            
            self.initialized_combo = True
            
        names = dict((i,i["ww_name"] or path_split(i.path)[-1]) for i in self.prefixes)
        names_values = names.values()
        for i in self.prefixes:
            model.append((id(i), None, names[i],
                "%s" % path_split(i.path)[-1]
                if names_values.count(names[i]) > 1 else ""))

        self.refresh_combo()
        
    def initialize_treeview(self):
        tree = self.xml.get_widget("treeview1")
        treeselection = tree.get_selection()

        model = tree.get_model()
        if isinstance(model, gtk.TreeModelSort):
            model = model.get_model()
        if self.initialized_treeview:
            model.clear()
            for i in model: model.remove(i.iter)
        else:
            col = gtk.TreeViewColumn("prefix")
            col_cell_img = gtk.CellRendererPixbuf()
            col.pack_start(col_cell_img, False)
            col.add_attribute(col_cell_img, "pixbuf", 1)

            col.set_sort_order(gtk.SORT_ASCENDING)
            col.set_sort_column_id(0)
            col_cell_text = gtk.CellRendererText()
            col.pack_start(col_cell_text, False)
            col.add_attribute(col_cell_text, "text", 0)

            col_cell_text2 = gtk.CellRendererText()
            col_cell_text2.set_property("weight", 300)
            col_cell_text2.set_property("scale", 0.8)
            col_cell_text2.set_property("ellipsize-set", pango.ELLIPSIZE_START)
            col.pack_start(col_cell_text2, False)
            col.add_attribute(col_cell_text2, "text", 4)

            col_cell_text3 = gtk.CellRendererText()
            col.pack_start(col_cell_text3, True)
            col.add_attribute(col_cell_text3, "text", 6)
            tree.append_column(col)
            
            model = gtk.TreeStore(str, gtk.gdk.Pixbuf, int, int, str, str, str)
            sortmodel = gtk.TreeModelSort(model)
            sortmodel.set_default_sort_func(self.default_treeview_sort)
            tree.set_model(sortmodel)
            treeselection.set_mode(gtk.SELECTION_SINGLE)
            self.initialized_treeview = True

        treeselection.set_select_function(self.handler_treeselect)

        imgdir = tree.render_icon(stock_id="gtk-directory", size=gtk.ICON_SIZE_MENU, detail=None)
        imgprefix = tree.render_icon(stock_id="gtk-harddisk", size=gtk.ICON_SIZE_MENU, detail=None)
        imgexe = tree.render_icon(stock_id="gtk-execute", size=gtk.ICON_SIZE_MENU, detail=None)
        imgerror = tree.render_icon(stock_id="gtk-dialog-error", size=gtk.ICON_SIZE_MENU, detail=None)

        names = dict((i, i["ww_name"] or path_split(i.path)[-1]) for i in self.prefixes)
        names_values = names.values()
        
        # ( name, pixbuf, id, type, comment, path, comment ) 
        for i in self.prefixes:
            broken = isinstance(i, BrokenPrefix)
            known = i.known_executables
            lk = len(known)
            li = model.append( None, (
                names[i],
                imgerror if broken else imgprefix,
                id(i),
                self.constant_treeview_broken_prefix 
                    if broken else self.constant_treeview_prefix,
                "%s" % path_split(i.path)[-1]
                    if names_values.count(names[i]) > 1 else "",
                i.path,
                "(%d application%s)" % (lk, "s" if lk > 1 else "")
                    if known else "" ))
            for j in known:
                broken = not isfile(j)
                model.append(li, (
                    path_split(j)[-1],
                    imgerror if broken else imgexe,
                    0,
                    self.constant_treeview_broken_executable
                        if broken else self.constant_treeview_executable,
                    "", j, "" ))
        self.refresh_treeview()
        
    def refresh_combo(self):
        combo = self.xml.get_widget("combobox1")
        
        if self.initialized_combo:
            if self.current_prefix is None: combo.set_active(-1)
            else:
                current_id = id(self.current_prefix)
                for i in combo.get_model():
                    if i[0] == current_id:
                        combo.set_active_iter(i.iter)
                        self.guiChange()
                        break
        else:
            self.initialize_combo()
                    
    def refresh_treeview(self):
        tree = self.xml.get_widget("treeview1")
        selection = tree.get_selection()
       
        if self.initialized_treeview:
            if self.current_prefix is None: selection.unselect_all()
            else:
                model = tree.get_model()
                prefix_id = id(self.current_prefix)
                for i in model:
                    if model.get_value(i.iter, 2) == prefix_id:
                        path = model.get_path(i.iter)
                        if not selection.iter_is_selected(i.iter):
                            selection.select_iter(i.iter)
                        tree.expand_row(path, True)
                        break
        else:
            self.initialize_treeview()

    def handler_iconview(self, iconview, path):
        model = iconview.get_model()
        command = model.get_value(model.get_iter(path), 2).tup
        self.action_run_at_prefix(self.current_prefix, command)

    def handler_error(self, code=None, message=None):
        if code == None:
            self.xml.get_widget("errorbox").set_property("visible", False)
        else:
            self.xml.get_widget("labelerror").set_label(message)
            self.xml.get_widget("errorbox").set_property("visible", True)
            
    def handler_launch(self, *args, **kwargs):
        winepath = (self.current_prefix.winepath or self.default_winepath,)
        if self.given_msi: command = winepath + ("msiexec", "/i") + self.given_msi
        elif self.given_exe:
            rpath = realpath(self.given_exe[0])
            if self.flag_remember:
                self.current_prefix.add_known_executable(rpath)
            else:
                self.current_prefix.remove_known_executable(rpath)
            command = winepath + self.given_exe
        else: command = winepath + self.given_cmd
        self.action_run_at_prefix(self.current_prefix, command)
        self.handler_quit()
        
    def handler_show_treeview(self, *args, **kwargs):
        self.refresh_treeview()
        self.xml.get_widget("aspectframe1").set_property("visible", False)
        self.xml.get_widget("hbox1").set_property("visible", True)
        self.xml.get_widget("hbox3").set_property("visible", False)
        
        #while gtk.events_pending(): gtk.main_iteration()
        
        tree = self.xml.get_widget("treeview1")
        model = tree.get_model()
        prefix_id = id(self.current_prefix)
        for i in model:
            if model.get_value(i.iter, 2) == prefix_id:
                tree.scroll_to_cell(model.get_path(i.iter), tree.get_column(0), True, 0, 0.5)
                break
    
    def handler_show_combo(self, *args, **kwargs):
        self.refresh_combo()
        self.xml.get_widget("aspectframe1").set_property("visible", True)
        self.xml.get_widget("hbox1").set_property("visible", False)
        self.xml.get_widget("hbox3").set_property("visible", True)
    
    def handler_menu_newprefix(self, *args):
        dialog = self.xml.get_widget("dialog2")
        self.xml.get_widget("button5").set_property("visible", True) # add button
        self.xml.get_widget("button7").set_property("visible", False) # ok button
        #dialog.set_property("visible", True)
        while True: # Repeat if not name is given
            response = dialog.run()
            dialog.hide()
            if response == 1:
                name = self.xml.get_widget("entry1").get_text().strip()
                if name:
                    prefix = Prefix(
                        namer(expandvars(
                            "$HOME/.local/share/wineprefixes/%s" % name)),
                        self.default_prefix_config)
                    prefix.memorize()
                    prefix["ww_name"] = name
                    self.prefixes_by_id[id(prefix)] = prefix
                    self.prefixes_by_path[prefix.path] = prefix
                    self.prefixes.append(prefix)
                    self.guiPrefix()
                    break
            else: break
    
    def handler_menu_addprefix(self, *args):
        dialog1 = gtk.FileChooserDialog(
            "Select prefix directory",
            self.xml.get_widget("window1"),
            gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_ADD, gtk.RESPONSE_OK))
        dialog1.set_local_only(True)
        while True:
            response = dialog1.run()
            dialog1.hide()
            if response == gtk.RESPONSE_OK:
                filename = dialog1.get_filename()
                prefix = Prefix(abspath(filename), self.default_prefix_config)
                dialog2 = self.xml.get_widget("dialog2")
                self.xml.get_widget("button5").set_property("visible", True) # add button
                self.xml.get_widget("button7").set_property("visible", False) # ok button
                self.xml.get_widget("entry1").set_text(prefix["ww_name"] or path_split(filename)[-1])
                response = dialog2.run()
                dialog2.hide()
                if response == 1:
                    name = self.xml.get_widget("entry1").get_text()
                    if prefix["ww_name"] != name: prefix["ww_name"] = name
                    if prefix["ww_ignore"] != None: prefix["ww_ignore"] = None
                    prefix.memorize()
                    self.prefixes_by_id[id(prefix)] = prefix
                    self.prefixes_by_path[prefix.path] = prefix
                    self.prefixes.append(prefix)
                    self.guiPrefix()
                    break
            else: break
        dialog1.destroy()
        
    def handler_menu_addexe(self, *args):
        fil = gtk.FileFilter()
        fil.set_name("Windows executable")
        fil.add_pattern("*.exe")
        dialog1 = gtk.FileChooserDialog(
            "Select executable or executables",
            self.xml.get_widget("window1"),
            gtk.FILE_CHOOSER_ACTION_OPEN,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_ADD, gtk.RESPONSE_OK))
        dialog1.set_local_only(True)
        dialog1.set_select_multiple(True)
        dialog1.add_filter(fil)
        response = dialog1.run()
        dialog1.hide()
        if response == gtk.RESPONSE_OK:
            
            tree = self.xml.get_widget("treeview1")
            model, items = tree.get_selection().get_selected_rows()
            treeiter = model.get_iter(items[0])
            row_type = model.get_value(treeiter, 3)
            prefix_id = None
            if row_type  == self.constant_treeview_prefix:
                prefix_id = model.get_value(treeiter, 2)
            elif row_type in (self.constant_treeview_broken_executable,
              self.constant_treeview_executable):
                prefix_id = model.get_value(model.iter_parent(treeiter), 2)
            if prefix_id:
                prefix = self.prefixes_by_id[prefix_id]
                filenames = dialog1.get_filenames()
                if filenames:
                    prefix.extend_known_executables(filenames)
                    self.guiExecutable()
        dialog1.destroy()

    def handler_remember(self, *args):
        self.flag_remember = self.xml.get_widget("checkbutton1").get_property("active")
        
    def handler_treebutton(self, widget, event):
        tree = self.xml.get_widget("treeview1")
        path_at_pos = tree.get_path_at_pos(int(event.x), int(event.y))
        if path_at_pos is None:
            tree.get_selection().unselect_all()
            self.current_prefix = None
            self.guiChange()
        if event.button == 3:
            menu = "menu1"
            disable = ()
            enable = ()
            if path_at_pos != None:
                model = tree.get_model()
                treeiter = model.get_iter(path_at_pos[0])
                treeselection = tree.get_selection()
                if not treeselection.iter_is_selected(treeiter):
                    treeselection.select_iter(treeiter)
                if treeiter:
                    a = model.get_value(treeiter, 3)
                    if a == self.constant_treeview_prefix:
                        menu = "menu2"
                        enable = ("menuitem10","menuitem13")
                    elif a == self.constant_treeview_broken_prefix:
                        menu = "menu2"
                        disable = ("menuitem10","menuitem13")
                    elif a == self.constant_treeview_executable:
                        menu = "menu3"
                        enable = ("menuitem14",)
                    elif a == self.constant_treeview_broken_executable:
                        menu = "menu3"
                        disable = ("menuitem14",)
            for i in disable:
                self.xml.get_widget(i).set_property("sensitive", False)
            for i in enable:
                self.xml.get_widget(i).set_property("sensitive", True)
            self.xml.get_widget(menu).popup( None, None, None, event.button, event.time)
        elif event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            if path_at_pos != None:
                model = tree.get_model()
                treeiter = model.get_iter(path_at_pos[0])
                #tree.get_selection().select_iter(treeiter)
                if treeiter:
                    a = model.get_value(treeiter, 3)
                    if a == self.constant_treeview_prefix:
                        directory = model.get_value(treeiter, 5)
                        if islink(directory): directory = realpath(directory)
                        self.action_open_directory(directory)
                    elif a == self.constant_treeview_executable:
                        prefix = self.prefixes_by_id[model.get_value(model.iter_parent(treeiter), 2)]
                        self.action_run_at_prefix(prefix, (
                            prefix.winepath or self.default_winepath,
                            model.get_value(treeiter, 5)))
                
    def handler_set_winepath(self, filechooserbutton):
        winepath = filechooserbutton.get_filename()
        if winepath: self.current_prefix.winepath = winepath
        else: self.current_prefix.winepath = None
        self.guiChange()
                
    def handler_reset_winepath(self, *args):
        self.xml.get_widget("filechooserbutton1").unselect_all()
        self.current_prefix["ww_wine"] = None
        elf.guiChange()
        
    def handler_reset_winemenubuilder(self, *args):
        self.xml.get_widget("checkbutton2").set_property("active", False)
        
    def handler_winemenubuilder_toggle(self, *args):
        if self.current_prefix:
            value = None
            if self.xml.get_widget("checkbutton2").get_property("active"):
                value = "1"
            if value != self.current_prefix["ww_winemenubuilder_disable"]:
                self.current_prefix["ww_winemenubuilder_disable"] = value
    
    def handler_treeselect(self, selection):
        t = time()
        if t - self.flag_treeview_click_time < 0.1: return True
        self.flag_treeview_click_time = t
        tree = self.xml.get_widget("treeview1")
        model = tree.get_model()
        selected = model.get_iter(selection)
        a = model.get_value(selected, 3)
        b = model.get_value(selected, 2)
        if b == 0: self.current_prefix = None
        else: self.current_prefix = self.prefixes_by_id[b]
        self.guiChange()
        return True
        
    def handler_menu_open_prefix(self, *args):
        tree = self.xml.get_widget("treeview1")
        model, items = tree.get_selection().get_selected_rows()
        treeiter = model.get_iter(items[0])
        directory = model.get_value(treeiter, 5)
        if islink(directory): directory = realpath(directory)
        self.action_open_directory(directory)
        
    def handler_menu_run_executable(self, *args):
        tree = self.xml.get_widget("treeview1")
        model, items = tree.get_selection().get_selected_rows()
        treeiter = model.get_iter(items[0])
        prefix = self.prefixes_by_id[model.get_value(model.iter_parent(treeiter), 2)]
        self.action_run_at_prefix(prefix, (
            prefix.winepath or self.default_winepath,
            model.get_value(treeiter, 5)))
            
    def handler_menu_rename_prefix(self, *args):
        dialog = self.xml.get_widget("dialog2")
        self.xml.get_widget("button5").set_property("visible", False) # add button
        self.xml.get_widget("button7").set_property("visible", True) # ok button
        tree = self.xml.get_widget("treeview1")
        model, rows = tree.get_selection().get_selected_rows()
        if len(rows) != 1: return
        prefix = self.prefixes_by_id[model.get_value(model.get_iter(rows[0]), 2)]
        default_name = path_split(prefix.path)[-1]
        current_name = prefix["ww_name"] or default_name
        while True: # Repeat if not name is given
            self.xml.get_widget("entry1").set_text(current_name)
            response = dialog.run()
            dialog.hide()
            if response == 1:
                name = self.xml.get_widget("entry1").get_text().strip()
                if name:
                    if name == default_name: prefix["ww_name"] = None
                    elif name != current_name: prefix["ww_name"] = name
                    self.guiPrefix()
                    break
            else: break
            
    def handler_menu_remove_prefix(self, *args):
        dialog = self.xml.get_widget("dialog3")
        tree = self.xml.get_widget("treeview1")
        model, items = tree.get_selection().get_selected_rows()
        if len(items) == 1:
            treeiter = model.get_iter(items[0])
            prefix = self.prefixes_by_id[model.get_value(treeiter, 2)]
            self.xml.get_widget("radiobutton2").set_property("sensitive", not prefix.imported)
            self.xml.get_widget("radiobutton1").set_property("active", True)
            response = dialog.run()
            dialog.set_property("visible", False)
            
            if response == 1:
                if (self.xml.get_widget("radiobutton2").get_property("active")
                  and not self.xml.get_widget("radiobutton1").get_property("active")):
                    rmtree(prefix.path)
                elif prefix.imported:
                    remove(prefix.path)
                else:
                    prefix["ww_ignore"] = "1"
                self.prefixes_by_id.pop(id(prefix))
                self.prefixes_by_path.pop(prefix.path)
                self.prefixes.remove(prefix)
                self.guiPrefix()

    def handler_menu_remove_executable(self, *args):
        tree = self.xml.get_widget("treeview1")
        model, items = tree.get_selection().get_selected_rows()
        for i in items:
            treeiter = model.get_iter(i)
            treeiter_parent = model.iter_parent(treeiter)
            prefix = self.prefixes_by_id[model.get_value(treeiter_parent, 2)]
            prefix.remove_known_executable(model.get_value(treeiter, 5))
        self.guiPrefix()

    def handler_combo(self, *args):
        combo = self.xml.get_widget("combobox1")
        active = combo.get_active()
        if active > -1:
            prefix = self.prefixes_by_id[combo.get_model()[active][0]]
            self.current_prefix = prefix
            self.guiChange()

    def handler_quit(self,*args):
        for i in self.killable_threads: killPopen(i)
        if gtk.main_level() > 0: gtk.main_quit()
        
    def handler_delete_event(self, widget, *args):
        widget.set_property("visible", False)
        return gtk.TRUE
            
    def guiStart(self):
        # Gui is started for first time (call this one once)
        show = ()
        hide = ()
        if self.flag_mode_config:
            show = ("button20",) # Close
            self.handler_show_treeview()
        elif self.given_msi:
            show = ("button8", "button12") # Install, Cancel
            self.handler_show_combo()
        elif self.given_exe:
            show = ("button1", "button12", "vbox15") # Launch, cancel, remember
            self.handler_show_combo()
        elif self.given_cmd:
            show = ("button1", "button12") # Launch, cancel
            self.handler_show_combo()
        else: # Nothing given (configmode)
            show = ("button20",) # Close

            self.handler_show_treeview()
        
        for i in show: self.xml.get_widget(i).set_property("visible", True)
        for i in hide: self.xml.get_widget(i).set_property("visible", False)
        
        if self.flag_remember:
            self.xml.get_widget("checkbutton1").set_property("active", True)
        
        self.xml.signal_autoconnect({
               "on_window1_destroy" : self.handler_quit,
               "on_button12_clicked" : self.handler_quit,
               "on_combobox1_changed" : self.handler_combo,
               "on_button1_clicked" : self.handler_launch,
               "on_button8_clicked" : self.handler_launch,
               "on_button16_clicked" : self.handler_show_treeview,
               "on_button2_clicked" : self.handler_show_combo,
               "on_checkbutton1_toggled" : self.handler_remember,
               "on_dialog1_delete_event" : self.handler_delete_event,
               "on_dialog2_delete_event" : self.handler_delete_event,
               "on_dialog3_delete_event" : self.handler_delete_event,
               "on_iconview1_item_activated" : self.handler_iconview,
               "on_treeview1_button_press_event" : self.handler_treebutton,
               "on_menuitem1_activate" : self.handler_menu_newprefix,
               "on_menuitem2_activate" : self.handler_menu_newprefix,
               "on_menuitem6_activate" : self.handler_menu_newprefix,
               "on_menuitem4_activate" : self.handler_menu_addprefix,
               "on_menuitem5_activate" : self.handler_menu_addprefix,
               "on_menuitem7_activate" : self.handler_menu_addprefix,
               "on_menuitem10_activate" : self.handler_menu_addexe,
               "on_menuitem11_activate" : self.handler_menu_addexe,
               "on_menuitem15_activate" : self.handler_menu_open_prefix,
               "on_menuitem14_activate" : self.handler_menu_run_executable,
               "on_menuitem13_activate" : self.handler_menu_rename_prefix,
               "on_menuitem3_activate" : self.handler_menu_remove_prefix,
               "on_menuitem12_activate" : self.handler_menu_remove_executable,
               "on_button3_clicked": self.handler_reset_winepath,
               "on_button4_clicked": self.handler_reset_winemenubuilder,
               "on_filechooserbutton1_file_set" : self.handler_set_winepath,
               "on_checkbutton2_toggled" : self.handler_winemenubuilder_toggle,
            })
 
    def guiExecutable(self):
        # Executable list is changed
        self.initialize_treeview()
 
    def guiPrefix(self):
        # Prefix list is changed
        self.initialize_combo()
        self.initialize_treeview()
    
    def guiChange(self): 
        # Gui is changed (current_prefix changed)
        iconview = self.xml.get_widget("iconview1")
        model = iconview.get_model()
        if model: model.clear()
        if isinstance(self.current_prefix, Prefix):
            wineprefix = self.current_prefix.path
            winepath = self.current_prefix.winepath or self.default_winepath
            if model: toolModel(winepath, wineprefix, model)
            else:
                iconview.set_model(toolModel(winepath, wineprefix, model))
                iconview.set_pixbuf_column(0)
                iconview.set_text_column(1)
            iconview.set_property("sensitive", True)
            self.xml.get_widget("scrolledwindow3").set_property("sensitive", True)
            
            # Prefix configuration
            winepath = self.current_prefix.winepath
            if winepath:
                self.xml.get_widget("filechooserbutton1").set_filename(winepath)
            else:
                self.xml.get_widget("filechooserbutton1").unselect_all()
            
            self.xml.get_widget("checkbutton2").set_property("active",
                self.current_prefix["ww_winemenubuilder_disable"] == "1")
            
        else:
            iconview.set_property("sensitive", False)
            self.xml.get_widget("scrolledwindow3").set_property("sensitive", False)
        
        # Dialog buttons and error
        error = None
        if self.current_prefix:
            show = True
            winepath = self.current_prefix.winepath or self.default_winepath
            if isinstance(self.current_prefix, BrokenPrefix):
                error = "Prefix is broken."
                show = False
            elif not winepath or not checkBin(winepath):
                error = "Wine binary not found."
                show = False
        else:
            show = False
        if error:
            self.xml.get_widget("labelerror").set_label(error)
            self.xml.get_widget("errorbox").set_property("visible", True)
        else:
            self.xml.get_widget("errorbox").set_property("visible", False)
        self.xml.get_widget("button1").set_property("sensitive", show) # Launch
        self.xml.get_widget("button8").set_property("sensitive", show) # Install

if len(sys_argv)>1 and sys_argv[1] in ("--help","-h"):
    print('''%s - an easy graphical tool for wineprefixing.
    Usage:
        pywinery [OPTIONS...] FILE [ARGs...]  Execute command on with wine.

    Options:
        -v, --version     Prints Wine and Pywinery's version.
        -x, --nogui       Run with autodetected prefix if possible.
        -d, --debug       Show debug messages.
        -c, --config      Force run as configuration mode.
        -h, --help        Show this help.
    ''' % sys_argv[0])
elif len(sys_argv)>1 and sys_argv[1] in ("--version","-v"):
    print("Pywinery %s, wine %s." % (
        ".".join(str(i) for i in __version__),
        ".".join(str(i) for i in getWineVersion())
        ))
else:
    if __name__ == "__main__":
        app = Main(sys_argv)
        app.run()
