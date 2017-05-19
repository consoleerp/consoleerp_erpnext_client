// Copyright (c) 2017, Console ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Consolidation', {
	refresh: function(frm) {
		frm.set_query("party_type", "items", function(frm, cdn, cdt) {
			return {
				"filters": [["name", "in", ["Customer", "Supplier"]]]
			}
		});
	}
});
