#!/usr/bin/env python
"""
_GetJobSlots_

Oracle implementation of Locations.GetJobSlots
"""

from WMCore.WMBS.MySQL.Locations.GetJobSlots import GetJobSlots as MySQLGetJobSlots

class GetJobSlots(MySQLGetJobSlots):
    """
    Identical to MySQL version
    """
