#!/usr/bin/python
# -*- coding: utf-8 -*-
from sys import exit as sys_exit, argv
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
    
from os.path import realpath, split as path_split, join as path_join, isfile, isdir, expandvars
from os import environ, listdir, linesep
from commands import getoutput
from subprocess import Popen
from distutils.dir_util import mkpath
from mimetypes import guess_type

def getBin(name):
    return getoutput("which %s" % name).strip()

def checkBin(name):
    return bool(getBin(name))
    
class LoopHalt(Exception):
    def __str__(self):
        return "Loop halted"

class Main(object):
    def __init__(self):
        guifile = "/usr/share/pywinery/gui.glade"
        localgui = path_join(realpath(path_split(argv[0])[0]),"gui.glade")
        if isfile(localgui):
            guifile = localgui
        
        self.xml = gtk.glade.XML(guifile)
        self.configfile = expandvars("$HOME/.config/pywinery/prefixes.config")

        self.have_params = len(argv)>1
        self.winebin = getBin("wine")
        if not bool(self.winebin):
            print "Wine not found"
            return
        
        self.msi = None
        
        if self.have_params:
            if isfile(argv[1]) and guess_type(realpath(argv[1]))[0].lower()=="application/x-msi":
                self.msi = realpath(argv[1])
            #self.xml.get_widget("expander1").set_property("visible", False)
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
            
        self.xml.get_widget("button13").set_property("visible",checkBin("wine-doors"))
        self.comboInit()
        dic = {"on_window1_destroy" : self.__quit,
               "on_button12_clicked" : self.__quit,
               "on_combobox1_changed" : self.combochange,
               "on_button1_clicked" : None,
               "on_button6_clicked" : self.adddir,
               "on_button7_clicked" : self.removeprefix,
               "on_button1_clicked" : lambda x: (self.execute([self.winebin]+argv[1:]),self.__quit()),
               "on_button8_clicked" : lambda x: (self.execute([self.winebin,"msiexec","/i",self.msi]),self.__quit()),
               "on_button2_clicked" : lambda x: self.execute("winecfg"),
               "on_button4_clicked" : lambda x: self.execute("winefile"),
               "on_button5_clicked" : lambda x: self.execute([self.winebin,"uninstaller"]),
               "on_button3_clicked" : lambda x: self.execute(["xdg-open",self.getComboValue()]),
               "on_button10_clicked" : lambda x: self.execute("wineprefixcreate"),
               "on_button11_clicked" : lambda x: self.execute(["xterm","-e","wine","cmd"]),
               "on_button13_clicked" : lambda x: self.execute("wine-doors"),
            }
        self.xml.signal_autoconnect(dic)
        self.xml.get_widget("window1").show()
        self.env = environ.copy()
        self.combochange()
        gtk.main()
        
    def comboInit(self):
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
        
        if isfile(self.configfile):
            f = open(self.configfile,"r")
            for i in f.readlines():
                model.append([i.strip()])
            f.close()
        else:
            mkpath(path_split(self.configfile)[0])
            open(self.configfile,"w").close()
            
        if self.have_params:
            path = argv[1]
            try:
                while len(path)>1:
                    for i in model:
                        if path==i[0]:
                            combo.set_active_iter(i.iter)
                            raise LoopHalt
                    path = path_split(path)[0]
            except LoopHalt:
                pass
            
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
        
    def addfilenames(self,list):
        if list:
            newitems = []
            combo = self.xml.get_widget("combobox1")
            model = combo.get_model()
            olditems = [i[0] for i in model]
            for i in list:
                if not i in olditems:
                    newitems.append(i+linesep)
                    model.append([i])
            f = open(self.configfile,"a")
            f.writelines(newitems)
            f.close()
            for i in model:
                if i[0] == list[-1]:
                    combo.set_active_iter(i.iter)
        
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
            f = open(self.configfile,"w")
            f.writelines([i[0]+linesep for i in model])
            f.close()
        
    def getComboValue(self):
        combo = self.xml.get_widget("combobox1")
        model = combo.get_model()
        return model[combo.get_active()][0]
        
    def combochange(self,*args):
        a = bool(self.xml.get_widget("combobox1").get_active() > -1)
        self.xml.get_widget("hbox6").set_property("sensitive", False)
        self.xml.get_widget("button7").set_property("sensitive", False)
        self.xml.get_widget("hbox1").set_property("sensitive", False)
        if a:
            path = self.getComboValue()
            if isdir(path):
                self.xml.get_widget("button7").set_property("sensitive", True)
                self.xml.get_widget("hbox1").set_property("sensitive", True)
                self.xml.get_widget("labelname").set_property("label", "on <b>%s</b>" % path_split(path)[1])
                b = True
                ls = listdir(path)
                for i in ("drive_c","dosdevices","user.reg","system.reg","userdef.reg"):
                    if i not in ls:
                        b = False
                        break

                self.xml.get_widget("hbox6").set_property("sensitive", b)
                self.xml.get_widget("button2").set_property("sensitive", b)
                self.xml.get_widget("button4").set_property("sensitive", b)
                self.xml.get_widget("button5").set_property("sensitive", b)
                self.xml.get_widget("button10").set_property("sensitive", not b)
                self.xml.get_widget("button11").set_property("sensitive", b)
                self.xml.get_widget("button13").set_property("sensitive", b)
                self.env["WINEPREFIX"] = path
            else:
                self.xml.get_widget("button7").set_property("sensitive", True)
                self.xml.get_widget("labelname").set_property("label", "<b>Directory not found</b>")
        else:
            self.xml.get_widget("labelname").set_property("label", "<b>None selected</b>")
        
    def __quit(self,*args):
        gtk.main_quit()
        
    def execute(self,command):
        Popen(command, env=self.env)   

if len(argv)>1 and argv[1] in ("--help","-h"):
    print '''pywinery - an easy graphical tool for wineprefix-ing
    Usage:
        pywinery [OPTIONS]            Allows pywinery call wine with this options
        pywinery PROGRAM [ARGUMENTS]  Allows pywinery call an exe with wine 
        pywinery --help               Display this help and exit
    '''
else:
    if __name__ == "__main__":
        Main()
