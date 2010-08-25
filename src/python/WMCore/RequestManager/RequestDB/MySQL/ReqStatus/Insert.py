#!/usr/bin/env python
"""
_ReqStatus.InsertSQL_

MySQL Support to insert a list of valid Request Status values

"""
__revision__ = "$Id: Insert.py,v 1.1 2010/07/01 19:09:29 rpw Exp $"
__version__ = "$Revision: 1.1 $"

#CHANGED FVL 1 line
#from WMCore.Database.DBFormatter import DBFormatter
from WMCore.RequestManager.RequestDB.Settings.RequestStatus import StatusList

#CHANGED FVL 2 line
from WMCore.Database.DBCreator import DBCreator
import threading


#CHANGED FVL multiple lines
class Insert(DBCreator):

    sql = "INSERT INTO reqmgr_request_status ( status_name ) VALUES "

    def __init__(self, logger=None, dbi=None):
        #myThread = threading.currentThread()
        #DBCreator.__init__(self, myThread.logger, myThread.dbi)
        DBCreator.__init__(self, logger, dbi)

        self.create = {}

        for status in StatusList[:-1]:
            self.sql += "(\'%s\')," % status
        self.sql += "(\'%s\') " % StatusList[-1]
        self.create['statement'] = self.sql

