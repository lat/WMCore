#!/usr/bin/env python

"""
_TestMonitor_

This is the test class for monitors
"""

import threading
import time
import logging
import os
import os.path
import signal
import traceback

from WMCore.WMRuntime.Monitors.WMRuntimeMonitor import WMRuntimeMonitor
from WMCore.WMSpec.Steps.Executor               import getStepSpace
from WMCore.WMSpec.WMStep                       import WMStepHelper
from WMCore.Algorithms.SubprocessAlgos          import tailNLinesFromFile

import WMCore.FwkJobReport.Report as Report

# Get the Dashboard information class
from WMCore.WMRuntime.DashboardInterface        import DashboardInfo

getStepName = lambda step: WMStepHelper(step).name()

def getStepPID(stepSpace, stepName):
    """
    _getStepPID_
    
    Find the PID for a step given its stepSpace from the file
    """
    currDir = stepSpace.location
    pidFile = os.path.join(currDir, 'process.id')
    if not os.path.isfile(pidFile):
        msg = "Could not find process ID file for step %s" % stepName
        logging.error(msg)
        return None
    
    filehandle = open(pidFile,'r')
    output = filehandle.read()
    
    try:
        stepPID = int(output)
    except ValueError:
        msg = "Couldn't find a number"
        logging.error(msg)
        return None

    return stepPID


def searchForEvent(file):
    """
    _searchForEvent_
    
    Searches for the last event output into the CMSSW output file
    """
    import re
    MatchRunEvent = re.compile("Run: [0-9]+ Event: [0-9]+$")

    #I'm just grabbing the last twenty lines for the hell of it
    lines = tailNLinesFromFile(file, 20)

    lastMatch = None
    for line in lines:
        if MatchRunEvent.search(line.strip()):
            matches = MatchRunEvent.findall(line.strip())
            lastMatch = matches[-1]

    if lastMatch != None:
        #  //
        # // Extract and update last run/event number
        #//
        try:
            runInfo, lastEvent = lastMatch.split("Event:", 1)
            lastRun =  int(runInfo.split("Run:", 1)[1])
            lastEvent = int(lastEvent)
            return (lastRun, lastEvent)
        except Exception:
            return (None, None)

    return (None, None)

class DashboardMonitor(WMRuntimeMonitor):
    """
    _DashboardMonitor_
    
    Run in the background and pass information to
    the DashboardInterface instance.

    If the job exceeds timeouts, kill the job
    """

    def __init__(self):
        self.startTime        = None
        self.currentStep      = None
        self.currentStepName  = None
        self.currentStepSpace = None
        self.softTimeOut      = None
        self.hardTimeOut      = None
        self.killFlag         = False
        self.cmsswFile        = None
        self.task             = None
        self.job              = None
        self.dashboardInfo    = None
        WMRuntimeMonitor.__init__(self)


    def initMonitor(self, task, job, logPath, args = {}):
        """
        Handles the monitor initiation

        """
        logging.info("In DashboardMonitor.initMonitor")

        self.task    = task
        self.job     = job
        self.logPath = logPath

        self.softTimeOut = args.get('softTimeOut', None)
        self.hardTimeOut = args.get('hardTimeOut', None)
        
        destHost = args.get('destinationHost', None)
        destPort = args.get('destinationPort', None)

        self.dashboardInfo = DashboardInfo(task = task, job = job)

        if destHost and destPort:
            logging.info("About to set destination to %s:%s" % (destHost, destPort)) 
            self.dashboardInfo.addDestination(host = destHost,
                                              port = destPort)


    def jobStart(self, task):
        """
        Job start notifier.
        """
        try:
            self.dashboardInfo.jobStart()
        except Exception, ex:
            logging.error(str(ex))
            logging.error(str(traceback.format_exc()))

        return


    def jobEnd(self, task):
        """
        Job End notification

        """
        try:
            self.dashboardInfo.jobEnd()
        except Exception, ex:
            logging.error(str(ex))
            logging.error(str(traceback.format_exc()))

        return

    def stepStart(self, step):
        """
        Step start notification

        """
        self.currentStep      = step
        self.currentStepName  = getStepName(step)
        self.currentStepSpace = None
        self.startTime        = time.time()
        try:
            self.dashboardInfo.stepStart(step = step)
        except Exception, ex:
            logging.error(str(ex))
            logging.error(str(traceback.format_exc()))
        return

    def stepEnd(self, step, stepReport):
        """
        Step end notification

        """
        self.currentStep      = None
        self.currentStepName  = None
        self.currentStepSpace = None
        try:
            self.dashboardInfo.stepEnd(step = step,
                                   stepReport = stepReport)
        except Exception, ex:
            logging.error(str(ex))
            logging.error(str(traceback.format_exc()))
        return


    def stepKilled(self, step):
        """
        Step killed notification

        """

        self.currentStep     = None
        self.currentStepName = None
        try:
            self.dashboardInfo.stepKilled(step = step)
        except Exception, ex:
            logging.error(str(ex))
            logging.error(str(traceback.format_exc()))
        return

    def jobKilled(self, task):
        """
        Killed job notification

        """
        try:
            self.dashboardInfo.jobKilled()
        except Exception, ex:
            logging.error(str(ex))
            logging.error(str(traceback.format_exc()))
        return


    def periodicUpdate(self):
        """
        Run on the defined intervals.

        """
        
        if not self.currentStep:
            #We're probably between steps
            return

        self.dashboardInfo.periodicUpdate()


        #Check for events
        if self.cmsswFile:
            run, event = searchForEvent(file)
            if run and event:
                #Then we actually found something, otherwise do nothing
                #Right now I don't know what to do
                pass

        #Do timeout
        if not self.softTimeOut:
            return


        if time.time() - self.startTime > self.softTimeOut:
            #Then we have to kill the process

            # If our stepName is None, we're inbetween steps.  Nothing to kill!
            if self.currentStepName == None:
                return

            # If our stepName is valid, then we may need the stepSpace
            if self.currentStepSpace == None:
                self.currentStepSpace = getStepSpace(self.currentStepName)

            #First, get the PID
            stepPID = getStepPID(self.currentStepSpace, self.currentStepName)
        
            #Now kill it!
            msg = ""
            msg += "Start Time: %s\n" % self.startTime
            msg += "Time Now: %s\n" % time.time()
            msg += "Timeout: %s\n" % self.softTimeOut
            msg += "Killing Job...\n"
            msg += "Process ID is: %s\n" % stepPID

            # If possible, write a FWJR
            report  = Report.Report()
            try:
                self.logPath = os.path.join(self.currentStepSpace.location,
                                            '../../../', os.path.basename(self.logPath))
                if os.path.isfile(self.logPath):
                    # We should be able to find existant job report.
                    # If not, we're in trouble
                    logging.debug("Found pre-existant error report in DashboardMonitor termination.")
                    report.load(self.logPath)
                report.addError(stepName = self.currentStepName, exitCode = 99901,
                                errorType = "JobTimeout", errorDetails = msg)
                report.save(self.logPath)
            except Exception, ex:
                # Basically, we can't write a log report and we're hosed
                # Kill anyway, and hope the logging file gets written out
                msg2 =  "Exception while writing out jobReport.\n"
                msg2 += "Aborting job anyway: unlikely you'll get any error report.\n"
                msg2 += str(ex)
                msg2 += str(traceback.format_exc()) + '\n'
                logging.error(msg2)

            
            if stepPID == None or stepPID == os.getpid():
                # Then we are supposed to kill things
                # that don't exist in separate processes:
                # Self-terminate
                msg += "WARNING: No separate process.  Watchdog will attempt self-termination."
                logging.error(msg)
                os.abort()
            if time.time() - self.startTime < self.hardTimeOut or not self.killFlag:
                msg += "WARNING: Soft Kill Timeout has Expired:"
                logging.error(msg)
                os.kill(stepPID, signal.SIGUSR2)
                self.killFlag = True
            elif self.killFlag:
                msg += "WARNING: Hard Kill Timeout has Expired:"
                logging.error(msg)
                os.kill(stepPID, signal.SIGTERM)
                killedpid, stat = os.waitpid(stepPID, os.WNOHANG)
                if killedpid == 0:
                    os.kill(stepPID, signal.SIGKILL)
                    killedpid, stat = os.waitpid(stepPID, os.WNOHANG)
                    if killedpid == 0:
                        logging.error("Can't kill job.  Out of options.  Waiting for system reboot.")
                        #Panic!  It's unkillable!
                        


        return
        
