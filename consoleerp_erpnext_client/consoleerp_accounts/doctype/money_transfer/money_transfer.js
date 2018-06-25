// Copyright (c) 2018, Console ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Money Transfer', {
	setup: function(frm) {
		
		frm.add_fetch("company", "default_employee_advance_account", "from_receivable_payable");
		frm.add_fetch("company", "default_employee_advance_account", "to_receivable_payable");
		
		const cashBankQuery = function(doc) {
			return doc.from_type == "Account" ? {
				filters: [
					["Account", "account_type", "in", ["Cash", "Bank"]],
					["Account", "root_type", "=", "Asset"],
					["Account", "is_group", "=",0],
					["Account", "company", "=", doc.company]
				]
			} : {};
		}
		frm.fields_dict["to"].get_query = cashBankQuery;
		frm.fields_dict["from"].get_query = cashBankQuery;
		
		if (frm.doc.__islocal) {
			// update date and time
			frm.doc.posting_date = frappe.datetime.now_date();
			frm.doc.posting_time = frappe.datetime.now_time();
		}
	}
});
