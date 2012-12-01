#!/usr/bin/env python
 
from distutils.core import setup
 
setup(name         = 'pywinery',
      version      = '0.2.1',
      description  = 'Wine prefix manager and launcher',
      author       = 'Spayder26',
      author_email = '<spayder26@gmail.com>',
      url          = '',
      license      = 'GPLv3',
      data_files   = [
            ('/usr/share/pywinery',['gui.glade']),
            ('/usr/share/icons/hicolor/scalable/apps',['pywinery.svg']),
            ('/usr/share/applications',["pywinery.desktop"])
                     ],
      scripts      = ['pywinery.py']
      )
