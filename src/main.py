#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""The script starts the application."""
from Tkinter import Tk

from app import Application

root = Tk()
app = Application(master=root)
app.mainloop()
