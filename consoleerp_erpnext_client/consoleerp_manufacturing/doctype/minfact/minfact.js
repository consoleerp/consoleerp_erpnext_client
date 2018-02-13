// Copyright (c) 2018, Console ERP and contributors
// For license information, please see license.txt

frappe.provide("consoleerp.manufacturing")

consoleerp.manufacturing.MinFactController = erpnext.TransactionController.extend({
	setup: function(doc) {
		this.setup_posting_date_time_check();
		this._super(doc);
	},
	refresh: function() {
		// erpnext/erpnext/public/js/utils.js
		// toggle visibility of naming series after and before save
		erpnext.toggle_naming_series();
		
		// erpnext/erpnext/public/js/utils.js
		// hide company if it is the only company
		// if 1+ company, set last selected company by default
		erpnext.hide_company();
		
		// stock_controller.js
		// shows the "Stock Ledger" Button
		this.show_stock_ledger();
		if (cint(frappe.defaults.get_default("auto_accounting_for_stock")) && cur_frm.doc.purpose == "Subcontract") {
			this.show_general_ledger();
		}
	}
});

$.extend(cur_frm.cscript, new consoleerp.manufacturing.MinFactController({frm: cur_frm}));