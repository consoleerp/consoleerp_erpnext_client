// Copyright (c) 2018, Console ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Money Transfer', {
	setup: function(frm) {
		
		frm.add_fetch("company", "default_employee_advance_account", "from_receivable_payable");
		frm.add_fetch("company", "default_employee_advance_account", "to_receivable_payable");
		
		frm.fields_dict["to"].get_query = function(doc) {
			return doc.to_type == "Account" ? {
				filters: [
					["Account", "account_type", "in", ["Cash", "Bank"]],
					["Account", "root_type", "=", "Asset"],
					["Account", "is_group", "=",0],
					["Account", "company", "=", doc.company]
				]
			} : {};
		};
		frm.fields_dict["from"].get_query = function(doc) {
			return doc.from_type == "Account" ? {
				filters: [
					["Account", "account_type", "in", ["Cash", "Bank"]],
					["Account", "root_type", "=", "Asset"],
					["Account", "is_group", "=",0],
					["Account", "company", "=", doc.company]
				]
			} : {};
		};
		
		if (frm.doc.__islocal) {
			// update date and time
			frm.doc.posting_date = frappe.datetime.now_date();
			frm.doc.posting_time = frappe.datetime.now_time();
		}
	
	},
	
	refresh: function(frm) {
		frm.events.show_general_ledger(frm);
	},
	
	show_general_ledger: function(frm) {
		if(frm.doc.docstatus==1) {
			frm.add_custom_button(__('Ledger'), function() {
				frappe.route_options = {
					"voucher_no": frm.doc.name,
					"from_date": frm.doc.posting_date,
					"to_date": frm.doc.posting_date,
					"company": frm.doc.company,
					group_by_voucher: 0
				};
				frappe.set_route("query-report", "General Ledger");
			}, "fa fa-table");
		}
	}
});
