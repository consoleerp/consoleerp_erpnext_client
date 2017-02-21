// Copyright (c) 2016, Console ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Implementation', {
	territory_branch : function(frm, cdt, cdn) {
		frappe.call({
			"method" : "consoleerp_erpnext_client.app_data.territory_branch.territory_branch_src.setup",
			callback : function(r) {
				if (r.message == "1"){
					msgprint("Success!");
				} else {
					msgprint("Failed");
				}
			}
		});
	}
});
