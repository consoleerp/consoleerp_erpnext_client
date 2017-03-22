// Copyright (c) 2016, Console ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Implementation', {
	territory_branch : function(frm, cdt, cdn) {
		
		var d = new frappe.ui.Dialog({
			'fields': [
				{'fieldname': 'ht', 'fieldtype': 'Text'}
			]
		});
		d.fields_dict.ht.$wrapper.html('Please wait..');
		d.show();
		
		frappe.after_ajax(function() {
		
			frappe.call({
				"method" : "consoleerp_erpnext_client.customizations.territory_branch.territory_branch_src.setup",
				callback : function(r) {
					d.hide();
					if (r.message == "1"){
						msgprint("Success!");
					} else {
						msgprint("Failed!");
					}									
				}
			});
		});					
	}
});

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

