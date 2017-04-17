cur_frm.add_fetch("consoleerp_territory", "consoleerp_abbr", "consoleerp_territory_abbr");

frappe.ui.form.on("Warehouse Transfer", {
	refresh: function(frm) {
		frm.set_query("from_warehouse", function() {
			return {
				filters : { "consoleerp_territory" : cur_frm.doc.consoleerp_territory, "is_group" : 0 }
			}
		});
		
		frm.set_query("s_warehouse", "items", function(doc, cdt, cdn) {
			return {
				filters : { "consoleerp_territory" : doc.consoleerp_territory, "is_group" : 0}
			}
		});
	},
	
	consoleerp_territory: function(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "from_warehouse", null);		
	}
});