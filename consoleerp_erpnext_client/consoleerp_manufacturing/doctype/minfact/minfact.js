// Copyright (c) 2018, Console ERP and contributors
// For license information, please see license.txt

frappe.provide("consoleerp.manufacturing");


frappe.ui.form.on("MinFact", {
	validate: function(frm) {
		if (frm.doc.purpose == "Subcontract")
			frm.doc.warehouse = frm.doc.supplier_warehouse;
	},
	production_item: function(frm) {
		var doc = frm.doc;
		frm.set_value("qty", 1);
		return frappe.call({
			method: "get_production_item_details",
			freeze: true,
			doc: doc,
			callback: function(r) {
				if (!r.exc) {
					doc.cost_center = r.cost_center;
					doc.expense_account = r.expense_account;
					frm.refresh_fields();
				}
			}
		});
	},
	purpose: function(frm) {
		frm.toggle_reqd("supplier", frm.doc.purpose == "Subcontract");
		frm.toggle_reqd("supplier_warehouse", frm.doc.purpose == "Subcontract");
		frm.toggle_reqd("production_rate", frm.doc.purpose == "Subcontract");
		frm.toggle_reqd("credit_to", frm.doc.purpose == "Subcontract");
		
		// manufacturing
		frm.toggle_reqd("warehouse", frm.doc.purpose == "Manufacture");
	},
	is_paid: function(frm) {
		frm.toggle_reqd("cash_bank_account", frm.doc.is_paid);
	}
});

consoleerp.manufacturing.MinFactController = erpnext.TransactionController.extend({
	setup: function(doc) {
		this.setup_posting_date_time_check();
		// TODO
		// warehouse queries: company. refer production order		
		// Set query for BOM
		this.frm.set_query("bom_no", function() {
			if (cur_frm.doc.production_item) {
				return{
					query: "erpnext.controllers.queries.bom",
					filters: {item: cstr(cur_frm.doc.production_item)}
				}
			} else msgprint(__("Please enter Production Item first"));
		});
		
		this.frm.set_query("batch_no", function() {
			if (cur_frm.doc.production_item) {
				return{
					filters: {item: cstr(cur_frm.doc.production_item)}
				}
			} else msgprint(__("Please enter Production Item first"));
		});
		
		// Set query for FG Item
		this.frm.set_query("production_item", function() {
			// return erpnext.queries.item({is_stock_item: 1});
			if (cur_frm.doc.purpose == "Subcontract") 
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
		this._super(doc)
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
		if (cint(frappe.defaults.get_default("auto_accounting_for_stock"))) {
			this.show_general_ledger();
		}
		
		this._super()
	},
	supplier: function() {
		var me = this;
		return frappe.call({
			method: "erpnext.accounts.party.get_party_account",
			args: {
				party_type: "Supplier",
				party: me.frm.doc.supplier,
				company: me.frm.doc.company
			},
			callback: function(r) {
				if (!r.exc) {
					me.frm.set_value("credit_to", r.message);
				}
			}
		});
	},
	additional_cost: function() {
		this.calculate_taxes_and_totals();
	},
	production_rate: function() {
		this.calculate_taxes_and_totals();
	},
	qty: function() {
		this.calculate_taxes_and_totals();
	},
	calculate_taxes_and_totals: function() {
		if (this.frm.doc.purpose == "Subcontract") {
			this.frm.set_value("total", this.frm.doc.production_rate * this.frm.doc.qty + (this.frm.doc.additional_cost || 0));
			
			var total_tax = 0;
			for (var tax in this.frm.taxes) {
				if (tax.rate) {
					total_tax += flt(tax.rate * this.frm.doc.total / 100, precision("total_taxes_and_charges"));
				}
			}
			this.frm.set_value("total_taxes_and_charges", total_tax);
			this.frm.set_value("grand_total", this.frm.doc.total_taxes_and_charges + this.frm.doc.total);
			
			this.set_in_company_currency(this.frm.doc, ["total_taxes_and_charges", "grand_total"]);
		} else {
			
		}
	},
	bom_no: function(frm) {
		this.fetch_raw_materials(frm);
	},
	fetch_raw_materials: function(frm) {
		return cur_frm.call({
			doc: cur_frm.doc,
			method: "get_items_from_bom",
			freeze: true,
			callback: function(r) {
				if(r.message["set_scrap_wh_mandatory"]){
					frm.toggle_reqd("scrap_warehouse", true);
				}
			}
		});
	}
});
$.extend(cur_frm.cscript, new consoleerp.manufacturing.MinFactController({frm: cur_frm}));