#!/usr/bin/env python
"""
_DashboardInterface_t_

"""

import threading
import logging
import unittest
import socket
import os
import os.path

from WMQuality.TestInit import TestInit

# We need the DataStructs versions of these
from WMCore.DataStructs.Job  import Job
from WMCore.DataStructs.File import File
from WMCore.DataStructs.Run  import Run

# We're going to need one of these
from WMCore.WMSpec.StdSpecs.ReReco  import rerecoWorkload, getTestArguments
from WMCore.FwkJobReport.Report     import Report

from WMCore.WMRuntime.DashboardInterface import DashboardInfo
from WMCore.WMRuntime.Bootstrap          import setupMonitoring

from WMCore.WMBase import getTestBase


class DashboardInterfaceTest(unittest.TestCase):
    """
    Test for the dashboard interface and its monitoring interaction

    Well, once I've written them it will be
    """


    def setUp(self):
        """
        Basically, do nothing

        """

        self.testInit = TestInit(__file__)
        self.testInit.setLogging()


        self.testDir = self.testInit.generateWorkDir()

        return


    def tearDown(self):
        """
        Clean up the test directory

        """

        self.testInit.delWorkDir()

        return


    def createWorkload(self):
        """
        Create a workload in order to test things

        """
        workload = rerecoWorkload("Tier1ReReco", getTestArguments())
        rereco = workload.getTask("DataProcessing")
        return workload

    def createTestJob(self):
        """
        Create a test job to pass to the DashboardInterface

        """

        job = Job(name = "ThisIsASillyName")

        testFileA = File(lfn = "/this/is/a/lfnA", size = 1024, events = 10)
        testFileA.addRun(Run(1, *[45]))
        testFileB = File(lfn = "/this/is/a/lfnB", size = 1024, events = 10)
        testFileB.addRun(Run(1, *[46]))

        job.addFile(testFileA)
        job.addFile(testFileB)

        job['id'] = 1

        return job


    def createReport(self, outcome = 0):
        """
        Create a test report

        """

        jobReport = Report()
        jobReport.addStep('cmsRun1')
        jobReport.setStepStartTime(stepName = 'cmsRun1')
        jobReport.setStepStopTime(stepName = 'cmsRun1')
        if outcome:
            jobReport.addError('cmsRun1', 200, 'FakeError', 'FakeError')

        return jobReport


    def setupJobEnvironment(self, name = 'test'):
        """
        _setupJobEnvironment_

        Make some sort of environment in which to run tests
        """

        os.environ['WMAGENT_SITE_CONFIG_OVERRIDE'] = os.path.join(getTestBase(),
                                            "WMCore_t/Storage_t",
                                            "T1_US_FNAL_SiteLocalConfig.xml")
        return

    def testASuccessfulJobMonitoring(self):
        """
        _testASuccessfulJobMonitoring_

        Check that the data packets make sense when a job completes successfully
        """

        # Get the necessary objects
        name     = 'testA'
        job      = self.createTestJob()
        workload = self.createWorkload()
        task     = workload.getTask(taskName = "DataProcessing")
        report   = self.createReport()

        # Fill the job environment
        self.setupJobEnvironment(name = name)

        # Instantiate DBInfo
        dbInfo   = DashboardInfo(job = job, task = task)
        dbInfo.addDestination('127.0.0.1', 8884)

        # Check jobStart information
        data = dbInfo.jobStart()
        self.assertEqual(data['MessageType'], 'JobStatus')
        self.assertEqual(data['StatusValue'], 'running')
        self.assertEqual(data['StatusDestination'], "T1_US_FNAL")
        self.assertEqual(data['taskId'], 'wmagent_Tier1ReReco')

        # Do the first step
        step = task.getStep(stepName = "cmsRun1")

        # Do the step start
        data = dbInfo.stepStart(step = step.data)
        self.assertNotEqual(data['jobStart'], None)
        self.assertEqual(data['jobStart']['ExeStart'], step.name())
        self.assertEqual(data['jobStart']['WNHostName'], socket.gethostname())
        self.assertEqual(data['ExeStart'], step.name())

        #Do the step end
        data = dbInfo.stepEnd(step = step.data, stepReport = report)
        self.assertEqual(data['ExeEnd'], step.name())
        self.assertEqual(data['ExeExitCode'], 0)
        self.assertTrue(data['ExeWCTime'] >= 0)

        #Do a second step
        step = task.getStep(stepName = "cmsRun1")

        #Do the step start (It's not the first step)
        data = dbInfo.stepStart(step = step.data)
        self.assertEqual(data['jobStart'], None)
        self.assertEqual(data['ExeStart'], step.name())

        #Do the step end
        data = dbInfo.stepEnd(step = step.data, stepReport = report)
        self.assertEqual(data['ExeEnd'], step.name())
        self.assertEqual(data['ExeExitCode'], 0)
        self.assertTrue(data['ExeWCTime'] >= 0)

        # End the job!
        data = dbInfo.jobEnd()
        self.assertEqual(data['ExeEnd'], "cmsRun1")
        self.assertEqual(data['JobExitCode'], 0)
        self.assertEqual(data['WrapperCPUTime'], 0)
        self.assertTrue(data['WrapperWCTime'] >= 0)
        self.assertNotEqual(data['JobExitReason'], "")

        return


    def testAFailedJobMonitoring(self):
        """
        _TestAFailedJobMonitoring_

        Simulate a job that completes but fails, check that the data sent is
        correct
        """

        # Get the necessary objects
        name     = 'testB'
        job      = self.createTestJob()
        workload = self.createWorkload()
        task     = workload.getTask(taskName = "DataProcessing")
        report   = self.createReport(outcome = 1)

        # Fill the job environment
        self.setupJobEnvironment(name = name)

        # Instantiate DBInfo
        dbInfo   = DashboardInfo(job = job, task = task)
        dbInfo.addDestination('127.0.0.1', 8884)

        # Check jobStart information
        data = dbInfo.jobStart()
        self.assertEqual(data['MessageType'], 'JobStatus')
        self.assertEqual(data['StatusValue'], 'running')
        self.assertEqual(data['StatusDestination'], "T1_US_FNAL")
        self.assertEqual(data['taskId'], 'wmagent_Tier1ReReco')

        # Do the first step
        step = task.getStep(stepName = "cmsRun1")

        # Do the step start
        data = dbInfo.stepStart(step = step.data)
        self.assertNotEqual(data['jobStart'], None)
        self.assertEqual(data['jobStart']['ExeStart'], step.name())
        self.assertEqual(data['jobStart']['WNHostName'], socket.gethostname())
        self.assertEqual(data['ExeStart'], step.name())

        #Do the step end
        data = dbInfo.stepEnd(step = step.data, stepReport = report)
        self.assertEqual(data['ExeEnd'], step.name())
        self.assertNotEqual(data['ExeExitCode'], 0)
        self.assertTrue(data['ExeWCTime'] >= 0)

        # End the job!
        data = dbInfo.jobEnd()
        self.assertEqual(data['ExeEnd'], "cmsRun1")
        self.assertNotEqual(data['JobExitCode'], 0)
        self.assertEqual(data['WrapperCPUTime'], 0)
        self.assertTrue(data['WrapperWCTime'] >= 0)
        self.assertNotEqual(data['JobExitReason'].find('cmsRun1'), -1)

        return

    def testAKilledJobMonitoring(self):
        """
        _TestAKilledJobMonitoring_

        Simulate a job that is killed check that the data sent is
        correct
        """

        # Get the necessary objects
        name     = 'testC'
        job      = self.createTestJob()
        workload = self.createWorkload()
        task     = workload.getTask(taskName = "DataProcessing")
        report   = self.createReport(outcome = 1)

        # Fill the job environment
        self.setupJobEnvironment(name = name)

        # Instantiate DBInfo
        dbInfo   = DashboardInfo(job = job, task = task)
        dbInfo.addDestination('127.0.0.1', 8884)

        # Check jobStart information
        data = dbInfo.jobStart()
        self.assertEqual(data['MessageType'], 'JobStatus')
        self.assertEqual(data['StatusValue'], 'running')
        self.assertEqual(data['StatusDestination'], "T1_US_FNAL")
        self.assertEqual(data['taskId'], 'wmagent_Tier1ReReco')

        # Do the first step
        step = task.getStep(stepName = "cmsRun1")

        # Do the step start
        data = dbInfo.stepStart(step = step.data)
        self.assertNotEqual(data['jobStart'], None)
        self.assertEqual(data['jobStart']['ExeStart'], step.name())
        self.assertEqual(data['jobStart']['WNHostName'], socket.gethostname())
        self.assertEqual(data['ExeStart'], step.name())

        #Do the step end
        data = dbInfo.stepEnd(step = step.data, stepReport = report)
        self.assertEqual(data['ExeEnd'], step.name())
        self.assertNotEqual(data['ExeExitCode'], 0)
        self.assertTrue(data['ExeWCTime'] >= 0)

        # Kill the job!
        data = dbInfo.jobKilled()
        self.assertEqual(data['ExeEnd'], "cmsRun1")
        self.assertNotEqual(data['JobExitCode'], 0)
        self.assertEqual(data['WrapperCPUTime'], 0)
        self.assertTrue(data['WrapperWCTime'] >= 0)
        self.assertNotEqual(data['JobExitReason'].find('killed'), -1)

        return

if __name__ == "__main__":
    unittest.main()
