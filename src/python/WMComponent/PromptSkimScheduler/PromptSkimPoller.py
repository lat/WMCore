#!/usr/bin/env python
"""
_PromptSkimPoller_

Poll T0AST for complete blocks and launch skims.
"""

import time
import threading
import logging
import sys
import os
import traceback

from WMCore.WorkerThreads.BaseWorkerThread import BaseWorkerThread

from WMCore.Agent.Harness import Harness
from WMCore.DAOFactory import DAOFactory
from WMCore.Database.DBFactory import DBFactory

from T0.State.Database.Reader import ListBlock
from T0.State.Database.Writer import InsertBlock

from T0.GenericTier0.Tier0DB import Tier0DB
from T0.RunConfigCache.Cache import Cache

from WMCore.WMSpec.StdSpecs.PromptSkim import PromptSkimWorkloadFactory
from WMCore.WMSpec.StdSpecs.Tier1PromptReco import Tier1PromptRecoWorkloadFactory
from WMCore.WorkQueue.WorkQueue import WorkQueue

class PromptSkimPoller(BaseWorkerThread):
    def __init__(self, config):
        BaseWorkerThread.__init__(self)
        self.config = config
        return

    def setup(self, parameters = None):
        """
        _setup_

        Setup all the parameters.
        """
        logging.info("PromptSkimScheduler Component Started")

        # Workload related parameters
        self.promptSkimFactory = PromptSkimWorkloadFactory()
        self.tier1PromptRecoFactory = Tier1PromptRecoWorkloadFactory()
        self.promptSkimWorkloads = {}
        self.promptRecoWorkloads = {}
        self.workloadCache = self.config.PromptSkimScheduler.workloadCache

        if not os.path.exists(self.workloadCache):
            os.makedirs(self.workloadCache)

        myThread = threading.currentThread()
        self.daoFactory = DAOFactory(package = "WMCore.WMBS", logger = logging,
                                     dbinterface = myThread.dbi)
        self.runConfigCache = None

        # Scram arch and path to cmssw needed to generate workflows.
        self.scramArch = self.config.PromptSkimScheduler.scramArch
        self.cmsPath = self.config.PromptSkimScheduler.cmsPath
        self.initCommand = self.config.PromptSkimScheduler.initCommand

        # Job splitting parameters
        self.minMergeSize = self.config.PromptSkimScheduler.minMergeSize
        self.maxMergeEvents = self.config.PromptSkimScheduler.maxMergeEvents
        self.maxMergeSize = self.config.PromptSkimScheduler.maxMergeSize
        self.maxMergeFiles = self.config.PromptSkimScheduler.maxMergeFiles

        self.t0astDBConn = None
        self.connectT0AST()

        self.workQueue = WorkQueue(CouchUrl = self.config.JobStateMachine.couchurl,
                                   DbName = self.config.PromptSkimScheduler.localWQDB,
                                   CacheDir = os.path.join(self.config.General.workDir, "WorkQueueCacheDir"))
        return

    def connectT0AST(self):
        """
        _connectT0AST_

        Create a T0AST DB connection object.
        """
        self.t0astDBConn = Tier0DB(connectionParameters = {},
                                   manageGlobal = False,
                                   initConnection = False)

        self.t0astDBConn.dbFactory = DBFactory(logging, self.config.PromptSkimScheduler.t0astURL)
        self.t0astDBConn.connect()
        return

    def algorithm(self, parameters = None):
        """
        _algorithm_

        Poll for transferred blocks and complete runs.
        """
        self.pollForTransferredBlocks()
        return

    def getRunConfig(self, runNumber):
        """
        _getRunConfig_

        Get a RunConfig instance for the given run number.
        """
        if not self.runConfigCache:
            self.runConfigCache = Cache(promptSkimming = True)
            self.runConfigCache.t0astDBConn = self.t0astDBConn
            self.runConfigCache.configCache = os.path.join(self.config.PromptSkimScheduler.workloadCache,
                                                           "RunConfig")

        return self.runConfigCache.getRunConfig(runNumber)
    def createTier1PromptRecoWorkloadsForBlock(self, acquisitionEra, processingScenario, recoConfig, blockInfo):
        """
        _createTier1PromptRecoWorkloadsForBlock_

        Check to see if we have already created promptreco workloads for the
        run/dataset that the block belongs to. If no workload exists create one
        and install it into WMBS.
        """
        (datasetPath, guid) = blockInfo["BLOCK_NAME"].split("#", 1)
        (primary, processed, tier) = datasetPath[1:].split("/", 3)
        workloadName = "Run%s-%s-%s-%s" % (blockInfo["RUN_ID"], primary, processed, "Tier1PromptReco")

        if self.promptRecoWorkloads.has_key(blockInfo["RUN_ID"]):
            if self.promptRecoWorkloads[blockInfo["RUN_ID"]].has_key(primary):
                workload = self.promptRecoWorkloads[blockInfo["RUN_ID"]][primary]
                workload.setBlockWhitelist(blockInfo["BLOCK_NAME"])
                specPath = os.path.join(self.workloadCache, workloadName, "%s.pkl" % guid)
                workload.setSpecUrl(specPath)
                workload.save(specPath)
                self.workQueue.queueWork(specPath, team = "PromptSkimming", request = workloadName)
                return

        writeTiers = []
        if recoConfig.DoReco:
            if recoConfig.WriteRECO:
                writeTiers.append("RECO")
            if recoConfig.WriteDQM:
                writeTiers.append("DQM")
            if recoConfig.WriteAOD:
                writeTiers.append("AOD")

        if len(recoConfig.AlcaProducers) > 0:
            writeTiers.append("ALCARECO")
        alcaProducers = recoConfig.AlcaProducers

        wfParams = {"AcquisitionEra": acquisitionEra,
                    "Requestor": "CMSPromptSkimming",
                    "InputDataset": datasetPath,
                    "CMSSWVersion": recoConfig.CMSSWVersion,
                    "ScramArch": self.scramArch,
                    "InitCommand": self.initCommand,
                    "CouchURL": self.config.JobStateMachine.couchurl,
                    "CouchDBName": self.config.JobStateMachine.configCacheDBName,
                    "ProcessingVersion": recoConfig.ProcessingVersion,
                    "ProcScenario": processingScenario,
                    "GlobalTag": recoConfig.GlobalTag,
                    "UnmergedLFNBase": "/store/unmerged",
                    "MergedLFNBase": "/store/data",
                    "MinMergeSize": self.minMergeSize,
                    "MaxMergeSize": self.maxMergeSize,
                    "MaxMergeEvents": self.maxMergeEvents,
                    "WriteTiers": writeTiers,
                    "AlcaSkims": alcaProducers,
                    "PromptSkims":  recoConfig.PromptSkims,
                    "StdJobSplitAlgo": "EventBased",
                    "StdJobSplitArgs": {"events_per_job": recoConfig.EventSplit},
                    "SkimJobSplitAlgo": "FileBased",
                    "SkimJobSplitArgs": {"files_per_job": 1,
                                         "include_parents": True},
                    "ValidStatus": "VALID"}

        workload = self.tier1PromptRecoFactory(workloadName, wfParams)
        workload.setOwner("CMSDataOps")
        workload.setBlockWhitelist(blockInfo["BLOCK_NAME"])

        if recoConfig.CustodialNode.find("MSS") != -1:
            site = recoConfig.CustodialNode[:-4]
        else:
            site = recoConfig.CustodialNode
        workload.setSiteWhitelist(site)

        if not os.path.exists(os.path.join(self.workloadCache, workloadName)):
            os.makedirs(os.path.join(self.workloadCache, workloadName))

        specPath = os.path.join(self.workloadCache, workloadName, "%s.pkl" % guid)
        workload.setSpecUrl(specPath)
        workload.save(specPath)

        self.workQueue.queueWork(specPath, team = "PromptSkimming", request = workloadName)

        if not self.promptRecoWorkloads.has_key(blockInfo["RUN_ID"]):
            self.promptRecoWorkloads[blockInfo["RUN_ID"]] = {}
        self.promptRecoWorkloads[blockInfo["RUN_ID"]][primary] = workload
        return


    def createPromptSkimWorkloadsForBlock(self, acquisitionEra, skimConfig, blockInfo):
        """
        _createPromptSkimWorkloadsForBlock_

        Check to see if we're already created skimming workloads for the
        run/dataset that the block belongs to.  If no workload exists create one
        and install it into WMBS.
        """
        (datasetPath, guid) = blockInfo["BLOCK_NAME"].split("#", 1)
        (primary, processed, tier) = datasetPath[1:].split("/", 3)
        workloadName = "Run%s-%s-%s-%s" % (blockInfo["RUN_ID"], primary, processed, skimConfig.SkimName)

        if self.promptSkimWorkloads.has_key(blockInfo["RUN_ID"]):
            if self.promptSkimWorkloads[blockInfo["RUN_ID"]].has_key(skimConfig.SkimName):
                workload = self.promptSkimWorkloads[blockInfo["RUN_ID"]][skimConfig.SkimName]
                workload.setBlockWhitelist(blockInfo["BLOCK_NAME"])
                specPath = os.path.join(self.workloadCache, workloadName, "%s.pkl" % guid)
                workload.setSpecUrl(specPath)
                workload.save(specPath)
                self.workQueue.queueWork(specPath, team = "PromptSkimming", request = workloadName)
                return

        if skimConfig.TwoFileRead:
            includeParents = True
        else:
            includeParents = False

        wfParams = {"AcquisitionEra": acquisitionEra,
                    "Requestor": "CMSPromptSkimming",
                    "CustodialSite": skimConfig.SiteName,
                    "BlockName": blockInfo["BLOCK_NAME"],
                    "InputDataset": datasetPath,
                    "CMSSWVersion": skimConfig.CMSSWVersion,
                    "ScramArch": self.scramArch,
                    "InitCommand": self.initCommand,
                    "CouchURL": self.config.JobStateMachine.couchurl,
                    "CouchDBName": self.config.JobStateMachine.configCacheDBName,
                    "ProcessingVersion": skimConfig.ProcessingVersion,
                    "GlobalTag": skimConfig.GlobalTag,
                    "CmsPath": self.cmsPath,
                    "SkimConfig": skimConfig.ConfigURL,
                    "UnmergedLFNBase": "/store/unmerged",
                    "MergedLFNBase": "/store/data",
                    "MinMergeSize": self.minMergeSize,
                    "MaxMergeSize": self.maxMergeSize,
                    "MaxMergeEvents": self.maxMergeEvents,
                    "StdJobSplitAlgo": "FileBased",
                    "StdJobSplitArgs": {"files_per_job": 1,
                                        "include_parents": includeParents},
                    "ValidStatus": "VALID"}

        workload = self.promptSkimFactory(workloadName, wfParams)
        workload.setOwner("CMSDataOps")

        if not os.path.exists(os.path.join(self.workloadCache, workloadName)):
            os.makedirs(os.path.join(self.workloadCache, workloadName))

        specPath = os.path.join(self.workloadCache, workloadName, "%s.pkl" % guid)
        workload.setSpecUrl(specPath)
        workload.save(specPath)

        self.workQueue.queueWork(specPath, team = "PromptSkimming", request = workloadName)

        if not self.promptSkimWorkloads.has_key(blockInfo["RUN_ID"]):
            self.promptSkimWorkloads[blockInfo["RUN_ID"]] = {}
        self.promptSkimWorkloads[blockInfo["RUN_ID"]][skimConfig.SkimName] = workload
        return

    def pollForTransferredBlocks(self):
        """
        _pollForTransferredBlocks_

        Poll T0AST for any blocks that have been migrated to DBS and generate
        skims for them.  Mark the blocks as "Skimmed" once any skims or promtprecos have been
        injected into the Tier1 WMBS.
        """
        logging.info("pollForTransferredBlocks(): Running...")

        candidateBlocks = ListBlock.listBlockInfoByStatus(self.t0astDBConn,
                                                          "Exported", "Migrated")

        logging.info("pollForTransferredBlocks(): Found %s blocks." % len(candidateBlocks))
        logging.info("pollForTransferredBlocks(): %s" % candidateBlocks)

        for candidateBlock in candidateBlocks:
            logging.info("pollForTransferredBlocks(): Candidate: %s" % candidateBlock["BLOCK_ID"])
            runConfig = self.getRunConfig(int(candidateBlock["RUN_ID"]))

            skims = runConfig.getSkimConfiguration(candidateBlock["PRIMARY_ID"],
                                                   candidateBlock["TIER_ID"])
            tier1RecoConfig = runConfig.getTier1PromptRecoConfiguration(candidateBlock["PRIMARY_ID"])

            if skims == None and tier1RecoConfig == None:
                InsertBlock.updateBlockStatusByID(self.t0astDBConn,
                                                  candidateBlock, "Skimmed")
                self.t0astDBConn.commit()
                logging.info("No skims or promptRecos for block %s" % candidateBlock["BLOCK_ID"])

            elif skims != None:
                insertParents = False
                for skimConfig in skims:
                    if skimConfig.TwoFileRead:
                        insertParents = True
                        break

                if insertParents:
                    if not ListBlock.isParentBlockExported(self.t0astDBConn, candidateBlock["BLOCK_ID"]):
                        logging.info("Block %s has unexported parents." % candidateBlock["BLOCK_ID"])
                        continue

                myThread = threading.currentThread()
                myThread.transaction.begin()

                for skimConfig in skims:
                    try:
                        self.createPromptSkimWorkloadsForBlock(runConfig.getAcquisitionEra(),
                                                    skimConfig, candidateBlock)
                    except Exception, ex:
                        logging.info("Error making workflows: %s" % str(ex))
                        logging.info("Traceback: %s" % traceback.format_exc())
                        self.t0astDBConn.rollback()
                        myThread.transaction.rollback()
                        break
                else:
                    InsertBlock.updateBlockStatusByID(self.t0astDBConn, candidateBlock,
                                                    "Skimmed")
                    self.t0astDBConn.commit()
                    myThread.transaction.commit()

            elif tier1RecoConfig != None:
                myThread = threading.currentThread()
                myThread.transaction.begin()

                try:
                    self.createTier1PromptRecoWorkloadsForBlock(runConfig.getAcquisitionEra(), runConfig.getScenario(candidateBlock["PRIMARY_ID"]),
                                                tier1RecoConfig, candidateBlock)
                except Exception, ex:
                    logging.error("Error making workflows: %s" % str(ex))
                    logging.error("Traceback: %s" % traceback.format_exc())
                    self.t0astDBConn.rollback()
                    myThread.transaction.rollback()
                    continue

                InsertBlock.updateBlockStatusByID(self.t0astDBConn, candidateBlock,
                                                "Skimmed")
                self.t0astDBConn.commit()
                myThread.transaction.commit()

        self.t0astDBConn.commit()
        return
