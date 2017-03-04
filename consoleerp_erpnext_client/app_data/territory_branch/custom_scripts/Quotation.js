cur_frm.add_fetch("consoleerp_territory", "consoleerp_abbr", "consoleerp_territory_abbr");

frappe.ui.form.on("Quotation", {
	refresh : function(frm) {
		frm.set_query("customer", function() {
			return {
				query : "consoleerp_erpnext_client.api.custom_link_queries.customer_query",
				filters : {"territory" : cur_frm.doc.consoleerp_territory}
			}
		});
	},
	validate : function(frm) {
		frm.doc.territory = frm.doc.consoleerp_territory;
	},
	
	// setting warehouse = null on territory change
	consoleerp_territory : function(frm, cdt, cdn) {		
		frappe.model.set_value(cdt, cdn, "customer", null);
	}
});