"""
MySQL implementation of NewFileset
"""
from WMCore.WMBS.MySQL.Base import MySQLBase

class NewFilesetSQL(MySQLBase):
    sql = "insert into wmbs_fileset (name) values (:fileset)"
    
    def format(self, result):
        return result
    
    def getBinds(self, fileset = None):
        return self.dbi.buildbinds(self.dbi.makelist(fileset), 'fileset')
    
    def execute(self, fileset = None, conn = None, transaction = False):
        result = self.dbi.processData(self.sql, self.getBinds(fileset), 
                         conn = conn, transaction = transaction)
        return self.format(result)