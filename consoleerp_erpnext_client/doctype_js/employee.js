frappe.ui.form.on("Employee", "refresh", function(frm) {	
	frm.set_query("type", "consoleerp_documents", function(doc, cdt, cdn) {				
		return {
			filters: {related_to: "Employee"}
		}
	});
});