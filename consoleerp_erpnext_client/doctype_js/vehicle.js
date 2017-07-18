frappe.ui.form.on("Vehicle", "refresh", function(frm) {	
	frm.set_query("type", "consoleerp_documents", function(doc, cdt, cdn) {				
		return {
			filters: {related_to: "Vehicle"}
		}
	});
});