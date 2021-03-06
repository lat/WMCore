#!/usr/bin/env python
"""
_MonteCarlo_t_

Unit tests for the Monte Carlo workflow.

"""

import unittest
import os
import threading

from WMCore.WMBS.Fileset import Fileset
from WMCore.WMBS.Subscription import Subscription
from WMCore.WMBS.Workflow import Workflow

from WMCore.WorkQueue.WMBSHelper import WMBSHelper
from WMCore.WMSpec.StdSpecs.MonteCarlo import getTestArguments, monteCarloWorkload

from WMQuality.TestInitCouchApp import TestInitCouchApp
from WMCore.Database.CMSCouch import CouchServer, Document


class MonteCarloTest(unittest.TestCase):
    def setUp(self):
        """
        _setUp_

        Initialize the database and couch.
        
        """
        self.testInit = TestInitCouchApp(__file__)
        self.testInit.setLogging()
        self.testInit.setDatabaseConnection()
        self.testInit.setupCouch("montecarlo_t", "ConfigCache")        
        self.testInit.setSchema(customModules = ["WMCore.WMBS"],
                                useDefault = False)

        couchServer = CouchServer(os.environ["COUCHURL"])
        self.configDatabase = couchServer.connectDatabase("rereco_t")        
        return


    def tearDown(self):
        """
        _tearDown_

        Clear out the database.
        
        """
        self.testInit.tearDownCouch()
        self.testInit.clearDatabase()
        return


    def injectMonteCarloConfig(self):
        """
        _injectMonteCarlo_

        Create a bogus config cache document for the montecarlo generation and
        inject it into couch.  Return the ID of the document.
        
        """
        newConfig = Document()
        newConfig["info"] = None
        newConfig["config"] = None
        newConfig["md5hash"] = "eb1c38cf50e14cf9fc31278a5c8e580f"
        newConfig["pset_hash"] = "7c856ad35f9f544839d8525ca10259a7"
        newConfig["owner"] = {"group": "cmsdataops", "user": "sfoulkes"}
        newConfig["pset_tweak_details"] ={"process": {"outputModules_": ["OutputA", "OutputB"],
                                                      "OutputA": {"dataset": {"filterName": "OutputAFilter",
                                                                              "dataTier": "RECO"}},
                                                      "OutputB": {"dataset": {"filterName": "OutputBFilter",
                                                                              "dataTier": "USER"}}}}
        result = self.configDatabase.commitOne(newConfig)
        return result[0]["id"]
    
    
    def _commonMonteCarloTest(self):
        """
        Retrieve the workload from WMBS and test all its properties.
        
        """
        prodWorkflow = Workflow(name = "TestWorkload",
                                task = "/TestWorkload/Production")
        prodWorkflow.load()

        self.assertEqual(len(prodWorkflow.outputMap.keys()), 3,
                         "Error: Wrong number of WF outputs.")

        goldenOutputMods = ["OutputA", "OutputB"]
        for goldenOutputMod in goldenOutputMods:
            mergedOutput = prodWorkflow.outputMap[goldenOutputMod][0]["merged_output_fileset"]
            unmergedOutput = prodWorkflow.outputMap[goldenOutputMod][0]["output_fileset"]

            mergedOutput.loadData()
            unmergedOutput.loadData()

            self.assertEqual(mergedOutput.name, "/TestWorkload/Production/ProductionMerge%s/merged-Merged" % goldenOutputMod,
                             "Error: Merged output fileset is wrong: %s" % mergedOutput.name)
            self.assertEqual(unmergedOutput.name, "/TestWorkload/Production/unmerged-%s" % goldenOutputMod,
                             "Error: Unmerged output fileset is wrong.")

        logArchOutput = prodWorkflow.outputMap["logArchive"][0]["merged_output_fileset"]
        unmergedLogArchOutput = prodWorkflow.outputMap["logArchive"][0]["output_fileset"]
        logArchOutput.loadData()
        unmergedLogArchOutput.loadData()

        self.assertEqual(logArchOutput.name, "/TestWorkload/Production/unmerged-logArchive",
                         "Error: LogArchive output fileset is wrong.")
        self.assertEqual(unmergedLogArchOutput.name, "/TestWorkload/Production/unmerged-logArchive",
                         "Error: LogArchive output fileset is wrong.")

        for goldenOutputMod in goldenOutputMods:
            mergeWorkflow = Workflow(name = "TestWorkload",
                                     task = "/TestWorkload/Production/ProductionMerge%s" % goldenOutputMod)
            mergeWorkflow.load()

            self.assertEqual(len(mergeWorkflow.outputMap.keys()), 2,
                             "Error: Wrong number of WF outputs.")

            mergedMergeOutput = mergeWorkflow.outputMap["Merged"][0]["merged_output_fileset"]
            unmergedMergeOutput = mergeWorkflow.outputMap["Merged"][0]["output_fileset"]

            mergedMergeOutput.loadData()
            unmergedMergeOutput.loadData()

            self.assertEqual(mergedMergeOutput.name, "/TestWorkload/Production/ProductionMerge%s/merged-Merged" % goldenOutputMod,
                             "Error: Merged output fileset is wrong.")
            self.assertEqual(unmergedMergeOutput.name, "/TestWorkload/Production/ProductionMerge%s/merged-Merged" % goldenOutputMod,
                             "Error: Unmerged output fileset is wrong.")

            logArchOutput = mergeWorkflow.outputMap["logArchive"][0]["merged_output_fileset"]
            unmergedLogArchOutput = mergeWorkflow.outputMap["logArchive"][0]["output_fileset"]
            logArchOutput.loadData()
            unmergedLogArchOutput.loadData()

            self.assertEqual(logArchOutput.name, "/TestWorkload/Production/ProductionMerge%s/merged-logArchive" % goldenOutputMod,
                             "Error: LogArchive output fileset is wrong: %s" % logArchOutput.name)
            self.assertEqual(unmergedLogArchOutput.name, "/TestWorkload/Production/ProductionMerge%s/merged-logArchive" % goldenOutputMod,
                             "Error: LogArchive output fileset is wrong.")

        topLevelFileset = Fileset(name = "TestWorkload-Production-SomeBlock")
        topLevelFileset.loadData()

        prodSubscription = Subscription(fileset = topLevelFileset, workflow = prodWorkflow)
        prodSubscription.loadData()

        self.assertEqual(prodSubscription["type"], "Production",
                         "Error: Wrong subscription type.")
        self.assertEqual(prodSubscription["split_algo"], "EventBased",
                         "Error: Wrong split algo.")

        for outputName in ["OutputA", "OutputB"]:
            unmergedOutput = Fileset(name = "/TestWorkload/Production/unmerged-%s" % outputName)
            unmergedOutput.loadData()
            mergeWorkflow = Workflow(name = "TestWorkload",
                                            task = "/TestWorkload/Production/ProductionMerge%s" % outputName)
            mergeWorkflow.load()
            mergeSubscription = Subscription(fileset = unmergedOutput, workflow = mergeWorkflow)
            mergeSubscription.loadData()

            self.assertEqual(mergeSubscription["type"], "Merge",
                             "Error: Wrong subscription type.")
            self.assertEqual(mergeSubscription["split_algo"], "ParentlessMergeBySize",
                             "Error: Wrong split algo: %s" % mergeSubscription["split_algo"])

        for outputName in ["OutputA", "OutputB"]:
            unmerged = Fileset(name = "/TestWorkload/Production/unmerged-%s" % outputName)
            unmerged.loadData()
            cleanupWorkflow = Workflow(name = "TestWorkload",
                                      task = "/TestWorkload/Production/ProductionCleanupUnmerged%s" % outputName)
            cleanupWorkflow.load()
            cleanupSubscription = Subscription(fileset = unmerged, workflow = cleanupWorkflow)
            cleanupSubscription.loadData()

            self.assertEqual(cleanupSubscription["type"], "Cleanup",
                             "Error: Wrong subscription type.")
            self.assertEqual(cleanupSubscription["split_algo"], "SiblingProcessingBased",
                             "Error: Wrong split algo.")

        procLogCollect = Fileset(name = "/TestWorkload/Production/unmerged-logArchive")
        procLogCollect.loadData()
        procLogCollectWorkflow = Workflow(name = "TestWorkload",
                                          task = "/TestWorkload/Production/LogCollect")
        procLogCollectWorkflow.load()
        logCollectSub = Subscription(fileset = procLogCollect, workflow = procLogCollectWorkflow)
        logCollectSub.loadData()

        self.assertEqual(logCollectSub["type"], "LogCollect",
                         "Error: Wrong subscription type.")
        self.assertEqual(logCollectSub["split_algo"], "MinFileBased",
                         "Error: Wrong split algo.")

        for outputName in ["OutputA", "OutputB"]:
            mergeLogCollect = Fileset(name = "/TestWorkload/Production/ProductionMerge%s/merged-logArchive" % outputName)
            mergeLogCollect.loadData()
            mergeLogCollectWorkflow = Workflow(name = "TestWorkload",
                                              task = "/TestWorkload/Production/ProductionMerge%s/Production%sMergeLogCollect" % (outputName, outputName))
            mergeLogCollectWorkflow.load()
            logCollectSub = Subscription(fileset = mergeLogCollect, workflow = mergeLogCollectWorkflow)
            logCollectSub.loadData()
            
            self.assertEqual(logCollectSub["type"], "LogCollect",
                             "Error: Wrong subscription type.")
            self.assertEqual(logCollectSub["split_algo"], "MinFileBased",
                             "Error: Wrong split algo.")
        

    def testMonteCarlo(self):
        """
        Create a Monte Carlo workflow and verify that it is injected correctly
        into WMBS and invoke its detailed test.        
        
        """
        defaultArguments = getTestArguments()
        defaultArguments["CouchURL"] = os.environ["COUCHURL"]
        defaultArguments["CouchDBName"] = "rereco_t"        
        defaultArguments["ProcConfigCacheID"] = self.injectMonteCarloConfig()

        testWorkload = monteCarloWorkload("TestWorkload", defaultArguments)
        testWorkload.setSpecUrl("somespec")
        testWorkload.setOwnerDetails("sfoulkes@fnal.gov", "DWMWM")
        
        testWMBSHelper = WMBSHelper(testWorkload, "Production", "SomeBlock")
        testWMBSHelper.createTopLevelFileset()
        testWMBSHelper.createSubscription(testWMBSHelper.topLevelTask, testWMBSHelper.topLevelFileset)
        
        self._commonMonteCarloTest()


    def testRelValMCWithPileup(self):
        """
        Create a Monte Carlo workflow and verify that it is injected correctly
        into WMBS and invoke its detailed test.
        The input configuration includes pileup input files.        
        
        """
        defaultArguments = getTestArguments()
        defaultArguments["CouchURL"] = os.environ["COUCHURL"]
        defaultArguments["CouchDBName"] = "rereco_t"        
        defaultArguments["ProcConfigCacheID"] = self.injectMonteCarloConfig()
        
        # add pile up configuration
        defaultArguments["PileupConfig"] = {"mc": ["/some/cosmics/dataset1","/some/cosmics/dataset2"],
                                            "data": ["/some/minbias/dataset3"]}

        testWorkload = monteCarloWorkload("TestWorkload", defaultArguments)
        testWorkload.setSpecUrl("somespec")
        testWorkload.setOwnerDetails("sfoulkes@fnal.gov", "DWMWM")
        
        testWMBSHelper = WMBSHelper(testWorkload, "Production", "SomeBlock")
        testWMBSHelper.createTopLevelFileset()
        testWMBSHelper.createSubscription(testWMBSHelper.topLevelTask, testWMBSHelper.topLevelFileset)
        
        self._commonMonteCarloTest()

        

if __name__ == '__main__':
    unittest.main()
