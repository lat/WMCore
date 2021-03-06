#!/usr/bin/env python
"""
_AnalysisRequest_
"""

from WMCore.RequestManager.RequestMaker.RequestMakerInterface import RequestMakerInterface
from WMCore.RequestManager.DataStructs.RequestSchema import RequestSchema
from WMCore.RequestManager.RequestMaker.Registry import registerRequestType
from WMCore.WMSpec.StdSpecs.Analysis import AnalysisWorkloadFactory


class AnalysisRequest(RequestMakerInterface):
    """
    _AnalysisRequest_

    """
    def __init__(self):
        RequestMakerInterface.__init__(self)

    def makeWorkload(self, schema):
        factory = AnalysisWorkloadFactory()
        return factory(schema['RequestName'], schema).data

class AnalysisSchema(RequestSchema):
    def __init__(self):
        RequestSchema.__init__(self)

        self.validateFields = []
        self.optionalFields = []

        self.validateFields = [
            "CMSSWVersion",
            "ScramArch",
            "InputDataset",
            "Requestor",
            "RequestorDN"
            ]
        self.optionalFields = [
            "SiteWhitelist",
            "SiteBlacklist",
            "BlockWhitelist",
            "BlockBlacklist",
            "RunWhitelist",
            "RunBlacklist",
            "CouchUrl",
            "CouchDBName",
            "DbsUrl",
            ]

    def validate(self):
        def _checkSiteList(list):
            if self.has_key(list) and hasattr(self,'allCMSNames'):
                for site in self[list]:
                    if not site in self.allCMSNames: #self.allCMSNames needs to be initialized to allow sitelisk check
                        raise RuntimeError("The site " + site + " provided in the " + list + " param has not been found. Check https://cmsweb.cern.ch/sitedb/json/index/SEtoCMSName?name= for a list of known sites")

        RequestSchema.validate(self)

        _checkSiteList("SiteWhitelist")
        _checkSiteList("SiteBlacklist")

        if self.get("RequestName").count(' ') > 0:
            raise RuntimeError("RequestName cannot contain spaces")

registerRequestType("Analysis", AnalysisRequest, AnalysisSchema)
