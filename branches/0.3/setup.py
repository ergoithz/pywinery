#!/usr/bin/env python

from distutils.core import setup
from pywinery import __version__

setup(name         = 'pywinery',
      version      = __version__,
      author       = 'Felipe A. Hernandez',
      author_email = '<spayder26@gmail.com>',
      url          = 'http://pywinery.googlecode.com',
      description  = 'Wine prefix launcher and manager',
      long_description = open('README.rst').read(),
      license      = 'GPLv3',
      classifiers  = [
            'Development Status :: 5 - Production/Stable',
            'Environment :: X11 Applications :: Gnome',
            'Intended Audience :: End Users/Desktop',
            'License :: OSI Approved :: GNU General Public License v3 (GPLv3',
            'Operating System :: POSIX',
            'Topic :: System :: Emulators',
            'Topic :: Utilities',
                     ],
      packages     = ['pywinery'],
      data_files   = [
            ('/usr/share/pywinery', [
                     'pywinery/gui.glade',
                     'pywinery/pywinery.svg'
                                    ]),
            ('/usr/share/applications', ["pywinery.desktop"]),
                     ],
      scripts      = ['scripts/pywinery']
      )
