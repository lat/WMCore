#!/usr/bin/env python
"""
_RetriedJobs_

MySQL implementation of Workflow.RetriedJobs
"""

__revision__ = "$Id: RetriedJobs.py,v 1.1 2010/06/17 14:22:43 sfoulkes Exp $"
__version__ = "$Revision: 1.1 $"

from WMCore.Database.DBFormatter import DBFormatter

class RetriedJobs(DBFormatter):
    sql = """SELECT wmbs_workflow.owner, wmbs_workflow.task, wmbs_job.id
                    FROM wmbs_workflow
               INNER JOIN wmbs_subscription ON
                 wmbs_workflow.id = wmbs_subscription.workflow
               LEFT OUTER JOIN wmbs_jobgroup ON
                 wmbs_subscription.id = wmbs_jobgroup.subscription
               LEFT OUTER JOIN wmbs_job ON
                 wmbs_jobgroup.id = wmbs_job.jobgroup
               LEFT OUTER JOIN wmbs_job_state ON
                 wmbs_job.state = wmbs_job_state.id
             WHERE wmbs_job.outcome = 0 AND wmbs_job.retry_count > 0 AND
                   (wmbs_job_state.name != 'exhausted' AND
                    wmbs_job_state.name != 'cleanout')"""
        
    def execute(self, conn = None, transaction = False):
        result = self.dbi.processData(self.sql, conn = conn, transaction = transaction)
        return self.formatDict(result)