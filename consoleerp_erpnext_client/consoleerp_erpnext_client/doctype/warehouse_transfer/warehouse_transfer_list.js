frappe.listview_settings["Warehouse Transfer"] = {
	add_fields: ["status"],
	get_indicator: function(doc) {
		if (doc.status === "Open") {
			return [__("Open"), "red", "status,=,Open"];
			
		} else if (doc.status === "Issued") {
			return [__("Issued"), "orange", "status,=,Issued"];
			
		} else if (doc.status === "Received") {
			return [__("Received"), "green", "status,=,Received"];
			
		}
	}
}