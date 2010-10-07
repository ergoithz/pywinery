#!/usr/bin/python
# -*- coding: utf-8 -*-
from sys import exit as sys_exit, argv as sys_argv
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
except:
    sys_exit(1)
    
from os.path import realpath, split as path_split, join as path_join, isfile, isdir, expandvars, dirname
from os import environ, listdir, sep, linesep, kill as os_kill
from commands import getoutput
from subprocess import Popen
from distutils.dir_util import mkpath
from mimetypes import guess_type
from threading import Thread
from time import sleep

def getBin(name):
    return getoutput("which %s" % name).strip()

def checkBin(name):
    return bool(getBin(name))
    
def killPopen(p, signal=15):
    if hasattr(p, "send_signal"):
        p.send_signal(signal)
    else:
        # For python < 2.6
        os_kill(p.pid, signal)
        
def getWineVersion():
    a = getoutput("wine --version")
    v = a.strip().split("-")[-1].split(".")
    tr = [0]*len(v)
    for i in xrange(len(tr)):
        tr[i] = int(v[i])
    return tuple(tr)

class LoopHalt(Exception):
    def __str__(self):
        return "Loop halted"
        
class ErrorManager(object):
    def __init__(self):
        self.__d = {}
        self.__l = []
        
    def add(self, id, message):
        self.__d[id] = message
        self.__l.append(id)
        
    def remove(self, id):
        while id in self.__l:
            self.__l.remove(id)
        
    def last(self):
        if self.isEmpty():
            return None
        return self.__d[self.__l[-1]]
            
    def isEmpty(self):
        return len(self.__l)==0

def returnFalse():
    return False
        

class Main(object):
    def __init__(self, args=None):
        if args==None:
            args = [__file__]
        guifile = "/usr/share/pywinery/gui.glade"
        localgui = path_join(dirname(args[0]),"gui.glade")
        if isfile(localgui):
            guifile = localgui
            
        self.killable_threads = []
        self.xml = gtk.glade.XML(guifile)
        self.configfile = expandvars("$HOME/.config/pywinery/prefixes.config")
        self.configlines = []
        self.readConfigFile()

        self.msi = None
        self.wineversion = [0]
        self.autocreateprefix = False
        self.errors = ErrorManager()
        
        self.winebin = getBin("wine")
        
        if not bool(self.winebin):
            self.showError("nowine","Wine is not detected on your system")
            self.xml.get_widget("expander1").set_property("visible", False)
            self.xml.get_widget("button1").set_property("visible", False)
            self.xml.get_widget("button8").set_property("visible", False)
            
        else:
            self.wineversion = getWineVersion()
            self.autocreateprefix = self.wineversion > (1,)
            self.xml.get_widget("button13").set_property("visible",checkBin("wine-doors"))
        
        
        self.silent = False
        self.nodebug = False
        c=1
        for i in args[1:]:
            if i[0]!="-":
                break # Given commands can contains - and -- too
            elif i in ("-x","--nogui"):
                self.silent = True
            elif i in ("-s","--silent"):
                self.nodebug = True
            c += 1
            
        self.zig = args[c:]
        self.favprefix = None
        self.path = None

        if self.zig:
            path = realpath(self.zig[0])
            self.path = dirname(path)
            sp = self.path.split(sep)
            for i in ("drive_c","c:"):
                if i in sp:
                    self.favprefix = sep.join(sp[:sp.index(i)])
                    if not self.favprefix in self.configlines:
                        self.unknowndir()
                    break
            
            if isfile(self.zig[0]) and guess_type(realpath(self.zig[0]))[0].lower()=="application/x-msi":
                self.msi = realpath(args[1])
            self.xml.get_widget("hbuttonbox1").set_property("visible", True)
            self.xml.get_widget("hbox2").set_property("visible", False)
            
            
            self.xml.get_widget("button1").set_property("visible", not bool(self.msi))
            self.xml.get_widget("button8").set_property("visible", bool(self.msi))
        else:
            self.xml.get_widget("expander1").set_expanded(True)
            self.xml.get_widget("hbuttonbox1").set_property("visible", False)
            self.xml.get_widget("hbox2").set_property("visible", True)
                
        for i in (11,1,3,4,5,6,7):
            self.xml.get_widget("label%d" % i ).set_property("visible",False)
            
        
        self.xml.get_widget("vbox10").set_property("visible",False)
        
        self.comboInit()
        dic = {"on_window1_destroy" : self.__quit,
               "on_button12_clicked" : self.__quit,
               "on_combobox1_changed" : self.combochange,
               "on_button1_clicked" : None,
               "on_button6_clicked" : self.adddir,
               "on_button7_clicked" : self.removeprefix,
               "on_button1_clicked" : self.runAndExit,
               "on_button8_clicked" : lambda x: (self.execute([self.winebin,"msiexec","/i",self.msi]), self.__quit()),
               "on_button2_clicked" : lambda x: self.execute("winecfg"),
               "on_button4_clicked" : lambda x: self.execute("winefile"),
               "on_button5_clicked" : lambda x: self.execute([self.winebin,"uninstaller"]),
               "on_button3_clicked" : lambda x: self.execute(["xdg-open",self.getComboValue()]),
               "on_button10_clicked" : self.createPrefix,
               "on_button11_clicked" : lambda x: self.execute(["xterm","-e","wine","cmd"]),
               "on_button13_clicked" : lambda x: self.execute("wine-doors"),
               "on_dialog1_delete_event" : returnFalse,
            }
        self.xml.signal_autoconnect(dic)
        self.env = environ.copy()
        if self.nodebug:
            self.env["WINEDEBUG"] = "-all"
        
    def readConfigFile(self):
        if isfile(self.configfile):
            f = open(self.configfile,"r")
            self.configlines = [i.strip() for i in f.readlines()]
            f.close()
            self.configlines.sort()
        else:
            self.writeConfigFile()
            
    def writeConfigFile(self):
        mkpath(path_split(self.configfile)[0])
        f = open(self.configfile,"w")
        f.writelines([ i+linesep for i in self.configlines ])
        f.close()
        
    def showError(self, id=None, message=None):
        if id==None:
            message = self.errors.last()
        else:
            self.errors.add( id, message )
        
        if message:
            self.xml.get_widget("labelerror").set_label(message)
            self.xml.get_widget("errorbox").set_property("visible",True)
        else:
            self.xml.get_widget("errorbox").set_property("visible",False)        
    
    def hideError(self,id=None):
        if id != None:
            self.errors.remove(id)
        self.showError()            
        
    def no_delete(self, w):
        w.hide()
        return True 
        
    def runAndExit(self, *args):
        self.execute( [self.winebin] + self.zig )
        self.__quit()
    
    def run(self):
        try:
            if self.silent:
                if self.zig:
                    if self.favprefix:
                        self.env["WINEPREFIX"] = self.favprefix
                        self.runAndExit()
                    else:
                        print "Pywinery is unable to find a suitable prefix."
                else:
                    print "Nothing to do"
                sys_exit(1)
            else:
                gtk.gdk.threads_init()
                self.xml.get_widget("window1").show()
                self.combochange()
                gtk.main()
        except KeyboardInterrupt:
            sys_exit(1)
        sys_exit(0)
        
    def comboInit(self,auto=True):
        combo = self.xml.get_widget("combobox1")
        new = True
        modelp = combo.get_model()
        if modelp != None:
            modelp.clear()
            combo.set_model(None)
            new = False
        model = gtk.ListStore(gobject.TYPE_STRING)
        combo.set_model(model)

        if new:
            render = gtk.CellRendererText()
            combo.pack_start(render)
            combo.add_attribute(render, 'text', 0)
        
        for i in self.configlines:
            model.append([i])
         
        if self.favprefix and auto:
            for i in model:
                if i[0]==self.favprefix:
                    combo.set_active_iter(i.iter)
                    break
            
    def adddir(self,*args):        
        dialog = gtk.FileChooserDialog(
            "Select a directory",
            self.xml.get_widget("window1"),
            gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            (gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_ADD,gtk.RESPONSE_OK))
                        
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.addfilenames(dialog.get_filenames())
        dialog.destroy()
        
    def unknowndir(self,*args):
        dialog = self.xml.get_widget("dialog1")
        response = dialog.run()
        if response == 1:
            self.addfilenames([self.favprefix])
        dialog.hide()
        
    def addfilenames(self,list):
        if list:
            a = len(self.configlines)
            self.configlines += list
            self.writeConfigFile()
            self.comboInit(auto=False)
            combo = self.xml.get_widget("combobox1")
            combo.set_active_iter(combo.get_model()[a].iter)
        
    def removeprefix(self,*args):
        combo = self.xml.get_widget("combobox1")
        model = combo.get_model()
        dialog = gtk.MessageDialog(
                    self.xml.get_widget("window1"),
                    gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                    gtk.MESSAGE_QUESTION,
                    gtk.BUTTONS_YES_NO,
                    ("¿Do you really want to remove <b>%s</b> dir from prefixes list?" % model[combo.get_active()][0])
                    )
        dialog.set_property("use-markup",True)
    
        response = dialog.run()
        dialog.destroy()
        if response==gtk.RESPONSE_YES:
            model.remove(model.get_iter(combo.get_active()))
            self.configlines = [i[0] for i in model]
            self.writeConfigFile()
        
    def getComboValue(self):
        combo = self.xml.get_widget("combobox1")
        model = combo.get_model()
        return model[combo.get_active()][0]
        
    def checkIsPrefix(self, path):
        ls = listdir(path)
        for i in ("drive_c","dosdevices","user.reg","system.reg","userdef.reg"):
            if i not in ls:
                return False
        return True
        
    def combochange(self,*args):
        eid = "dirnotfound"
        self.hideError(eid)
        
        a = bool(self.xml.get_widget("combobox1").get_active() > -1)
        self.xml.get_widget("button1").set_property("sensitive", False)
        self.xml.get_widget("button8").set_property("sensitive", False)
        self.xml.get_widget("button7").set_property("sensitive", False)
        self.xml.get_widget("hbox1").set_property("sensitive", False)
        if a:
            self.xml.get_widget("button7").set_property("sensitive", True)
            path = self.getComboValue()
            if isdir(path):
                if bool(self.winebin):
                    self.xml.get_widget("hbox1").set_property("sensitive", True)
                    
                    t = self.checkIsPrefix(path)
                    b = self.autocreateprefix or t

                    self.xml.get_widget("button1").set_property("sensitive", b)
                    self.xml.get_widget("button8").set_property("sensitive", b)
                    self.xml.get_widget("button2").set_property("sensitive", b)
                    self.xml.get_widget("button4").set_property("sensitive", b)
                    self.xml.get_widget("button5").set_property("sensitive", b)
                    self.xml.get_widget("button10").set_property("sensitive", not t)
                    self.xml.get_widget("button11").set_property("sensitive", b)
                    self.xml.get_widget("button13").set_property("sensitive", b)
                    self.env["WINEPREFIX"] = path
                    
            else:
                self.showError(eid,"Directory not found.")
            
        
    def __quit(self,*args):
        for i in self.killable_threads:
            killPopen(i)
        if gtk.main_level()>0:
            gtk.main_quit()

        
    def createPrefix(self, path):
        if self.autocreateprefix:
            p = self.execute(["wineboot","-i"])
        else:
            p = self.execute("wineprefixcreate")
            
        pid = len(self.killable_threads)
        self.killable_threads.append( p )
        
        path = self.env["WINEPREFIX"]
        
        tohide = ( "expander1", "hbox3" )
        states = [ self.xml.get_widget(i).get_property("visible") for i in tohide ]
        
        def wait():
            while True:
                poll = p.poll()
                if (poll == 0 and self.checkIsPrefix(path)) or poll != None:
                    break
                sleep(0.25)
                gtk.gdk.threads_enter()
                self.xml.get_widget("progressbar1").pulse()
                gtk.gdk.threads_leave()
            
            gtk.gdk.threads_enter()
            self.xml.get_widget("progressbar1").set_fraction(1)
            gtk.gdk.threads_leave()
            sleep(0.5)
            gtk.gdk.threads_enter()
            for i in range(len(tohide)):
                self.xml.get_widget( tohide[i] ).set_property( "visible", states[i] )
            self.xml.get_widget("vbox10").set_property("visible",False)
            self.killable_threads.pop(pid)
            self.combochange()
            self.xml.get_widget("button10").set_property("sensitive",False)
            gtk.gdk.threads_leave()
            
        def terminate(*args):
            killPopen(p)
        
        for i in tohide:
            self.xml.get_widget(i).set_property("visible", False)   
            
        self.xml.signal_autoconnect({"on_button9_clicked":terminate})
        self.xml.get_widget("progressbar1").set_fraction(0)
        self.xml.get_widget("label14").set_label("<b>%s</b>" % path)
        self.xml.get_widget("vbox10").set_property("visible",True)
        
        Thread(target=wait).start()
        
    def execute(self,command):
        return Popen(command, env=self.env)   

if len(sys_argv)>1 and sys_argv[1] in ("--help","-h"):
    print '''pywinery - an easy graphical tool for wineprefixing
    Usage:
        pywinery [OPTIONS...] FILE [ARGs...]  Call an exe with wine.

    Options:
        -x, --nogui       Run with autodetected prefix.
        -s, --silent      Hide winedebug messages.
        -h, --help        Show this help.
    '''
else:
    if __name__ == "__main__":
        app = Main(sys_argv)
        app.run()
