"""
    Demo.py is intended to demonstrate the module GlobalDictionary.py, a module 
    for interfacing with a TradeStation Easylanguage GlobalDictionary through a 
    COM object.

    The module requires that win32com (pywin32) be installed in your environment.

    Steps to install pywin32:

    1. Start a command line with administrator rights
    2. python -m pip install pywin32
    3. python pywin32_postinstall.py -install

    The location of pywin32_postinstall.py in my environment for example was:
    
    ~\AppData\Local\Programs\Python\Python38-32\Scripts\pywin32_postinstall.py 

    Python 3.8.0 (tags/v3.8.0:fa919fd, Oct 14 2019, 19:21:23)

"""

__author__ = "JohnR"
__date__ = "11/20/2019"
__version__ = "00.00.05"

import GlobalDictionary
import pythoncom
import signal
import time

# Define events for GlobalDictionary 
# Note the different function signatures for each event
def GD_add(self, key, value, size):
    print(f'*Add event for {self.name}* Key {key} added with value {value} -> New size: {size}')

def GD_remove(self, key, size):
    print(f'*Remove event for {self.name}* Removed key {key}')

def GD_change(self, key, value, size):
    print(f'*Change event for {self.name}* Key {key} changed to {value}')

def GD_clear(self):
    print(f'*Clear event for {self.name}*')

# Create global dictionary with optional events
GD = GlobalDictionary.create("DEMO", add=GD_add, remove=GD_remove, change=GD_change, clear=GD_clear)

simple_list = [1, 2, 3]
large_list = [n for n in range(1, 51)]
complex_list = [1, "String", True, [1.1, ['one', 'two']], {'a': 10, 'b': 20}]
complex_dict = {'A': 1.1, 'B': 2.2, 'C': 3.3, 'D': ['one', 'two', {'k1': 'v1', 'k2': 'v2'}]}

print('==================================DEMO=====================================') 

GD.clear() 
GD.add("BOOL", False)
GD["FLOAT"] = 3.141
GD["INT"] =  10
GD["STRING"] = "test string"
GD["SIMPLE_LIST"] = simple_list
GD["LARGE_LIST"] = large_list
GD["COMPLEX_LIST"] = complex_list
GD["COMPLEX_DICT"] = complex_dict
GD["ITEM_TO_REMOVE"] = 100
GD["ITEM_TO_REMOVE"] = 200
GD.set("ITEM_TO_REMOVE", 300)
GD.remove("ITEM_TO_REMOVE")

keys = GD.keys

print('\n==================================SIZE=====================================')
print(len(GD))
print('\n==================================KEYS=====================================')
print(keys)
print('\n==================================PAIRS====================================') 
for key in keys:
    print(f'{key}: {GD[key]}')
print('\n==================================EVENTS===================================') 

# Prevent application from exiting and allow for handling of GlobalDictionary events
while True:
    pythoncom.PumpWaitingMessages()
    time.sleep(0.01)  # Avoids high CPU usage by not checking constantly