var elementTable = function(divID) {
        
    var formatUrl = function(elCell, oRecord, oColumn, sData) { 
            elCell.innerHTML = "<a href='" + oRecord.getData("child_queue") + "' target='_blank'>" + sData + "</a>"; 
        };
        
	var dateFormatter = function(elCell, oRecord, oColumn, oData) {
        
        var oDate = new Date(oData*1000);
		//for the formatting check 
		// http://developer.yahoo.com/yui/docs/YAHOO.util.Date.html#method_format
        var str = YAHOO.util.Date.format(oDate, { format:"%D %T"});
        elCell.innerHTML = str;
    }
		
    var dataSchema = {
        fields: [{key: "id"}, {key: "spec_name"}, {key: "task_name"}, {key: "element_name"}, 
                 {key: "status"}, {key: "child_queue", formatter:formatUrl}, 
                 {key: "parent_flag"},
                 {key: "priority"}, {key: "num_jobs"},
                 {key: "parent_queue_id"}, {key: "subscription_id"},
                 {key: "insert_time", formatter:dateFormatter},
                 {key: "update_time", formatter:dateFormatter}
                ]
        };

    var dataUrl = "/workqueue/elementsinfo"

    var dataSource = WMCore.WebTools.createDataSource(dataUrl, dataSchema)
    
    tableConfig = WMCore.WebTools.defaultTableConfig;
    
    tableConfig.paginator = new YAHOO.widget.Paginator({rowsPerPage : 10});
    
    var dataTable = WMCore.WebTools.createDataTable(divID, dataSource, 
                         WMCore.WebTools.createDefaultTableDef(dataSchema.fields),
                         tableConfig, 100000);
}