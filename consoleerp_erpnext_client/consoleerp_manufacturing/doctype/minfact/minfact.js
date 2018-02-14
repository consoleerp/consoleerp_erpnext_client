// Copyright (c) 2018, Console ERP and contributors
// For license information, please see license.txt

frappe.provide("consoleerp.manufacturing");

// FROM buying.js
cur_frm.cscript.tax_table = "Purchase Taxes and Charges";
{% include 'erpnext/accounts/doctype/purchase_taxes_and_charges_template/purchase_taxes_and_charges_template.js' %}

frappe.ui.form.on("MinFact", {
	production_item: function(frm) {
		show_alert(frm.doc.production_item);
	}
});

consoleerp.manufacturing.MinFactController = erpnext.TransactionController.extend({
	setup: function(doc) {
		this.setup_posting_date_time_check();
		// TODO
		// warehouse queries: company. refer production order
		
		// Set query for BOM
		this.frm.set_query("bom_no", function() {
			if (frm.doc.production_item) {
				return{
					query: "erpnext.controllers.queries.bom",
					filters: {item: cstr(frm.doc.production_item)}
				}
			} else msgprint(__("Please enter Production Item first"));
		});
		
		// Set query for FG Item
		this.frm.set_query("production_item", function() {
			// return erpnext.queries.item({is_stock_item: 1});
			if (doc.purpose == "Subcontract") 
				return {
					query: "erpnext.controllers.queries.item_query",
					filters:{
						'is_sub_contracted_item': 1
					}
				}
			else 
				return {
					query: "erpnext.controllers.queries.item_query",
					filters:{
						'is_stock_item': 1
					}
				}
		});
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
	},
	rate: function() {
		this.re_calculate();
	},
	qty: function() {
		this.re_calculate();
	},
	re_calculate: function() {
		if (this.frm.doc.purpose == "Subcontract") {
			this.frm.set_value("total", this.frm.doc.rate * this.frm.doc.qty);
			this.calculate_taxes_and_totals();
		}
	}
});
$.extend(cur_frm.cscript, new consoleerp.manufacturing.MinFactController({frm: cur_frm}));