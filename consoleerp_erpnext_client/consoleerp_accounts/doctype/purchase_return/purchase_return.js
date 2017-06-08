// Copyright (c) 2017, Console ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Purchase Return', {
	setup: function(frm) {		
		$.extend(cur_frm.cscript, new consoleerp.purchase_return({frm:frm}));
	}
});


{% include 'erpnext/public/js/controllers/buying.js' %};

frappe.provide("consoleerp");
consoleerp.purchase_return = erpnext.buying.BuyingController.extend({
	setup: function(doc) {
		
		// defined in StockController.js
		this.setup_posting_date_time_check();
		this._super(doc);
		
		// Credit To
		// ----------------------------
		this.frm.set_query("debit_to", function(doc) {
			// filter on Account
			if (doc.supplier) {
				return {
					filters: {
						'account_type': 'Payable',
						'is_group': 0,
						'company': doc.company
					}
				}
			} else {
				return {
					filters: {
						'report_type': 'Balance Sheet',
						'is_group': 0,
						'company': doc.company
					}
				}
			}
		});		
		
		// Cash Bank Account
		// --------------------------------------		
		this.frm.set_query("cash_bank_account", function(doc) {
			return {
				filters: [
					["Account", "account_type", "in", ["Cash", "Bank"]],
					["Account", "root_type", "=", "Asset"],
					["Account", "is_group", "=",0],
					["Account", "company", "=", doc.company]
				]
			}
		});
		
		
		// Income Account in Details Table
		// --------------------------------------
		this.frm.set_query("expense_account", "items", function(doc) {
			return {
				query: "erpnext.controllers.queries.get_expense_account",
				filters: {'company': doc.company}
			}
		});
		

		// Cost Center in Details Table
		// -----------------------------
		cur_frm.fields_dict["items"].grid.get_field("cost_center").get_query = function(doc) {
			return {
				filters: {
					'company': doc.company,
					"is_group": 0
				}
			}
		}
		
		// Outstanding Amount
		// This is left out by calculate_taxes_and_totals() function since this is not an Invoice for it
		// Have to call calculate outstanding amount each time it is changed
			
	},
	
	// Override the taxes_and_totals method, call the _super(), 
	// calculate outstanding amount
	calculate_taxes_and_totals: function() {					
		this._super();
		this.calculate_outstanding_amount(true);
	},
		
	
	refresh: function() {
		this._super();
		//
		erpnext.toggle_naming_series();
		erpnext.hide_company();
		
		this.show_general_ledger()
		this.show_stock_ledger()
	},
	
	
	// Supplier
	// --------------------------------------
	
	supplier: function() {
		var me = this;
		if(this.frm.updating_party_details) 	return;
		
		erpnext.utils.get_party_details(this.frm, "erpnext.accounts.party.get_party_details",
			{
				posting_date: this.frm.doc.posting_date,
				party: this.frm.doc.supplier,
				party_type: "Supplier",
				account: this.frm.doc.credit_to,
				price_list: this.frm.doc.buying_price_list,
			}, function() {
				me.apply_pricing_rule();
			});
			
		// party account
		// it was supposed to be returned by get_party_details function
		// but it is returned only when doctype = Sales/Purchase Invoice
		frappe.call({
			method: "erpnext.accounts.party.get_party_account",
			args: {
				party_type: 'Supplier',
				party: this.frm.doc.supplier,
				company: this.frm.doc.company
			},
			callback: function(r) {
				if (r.message)
					me.frm.set_value("credit_to", r.message);
			}
		});
	},
	
	// Is Pos
	// --------------------------------------------------
	is_paid: function(frm){
		this.hide_fields(this.frm.doc);
		if(cint(this.frm.doc.is_paid)) {
			if(!this.frm.doc.company) {
				this.frm.set_value("is_paid", 0)
				frappe.msgprint(__("Please specify Company to proceed"));
			}
		}
		this.calculate_outstanding_amount();
		this.frm.refresh_fields();
	},
	
	
	calculate_outstanding_amount: function(update_paid_amount) {
		//
		// referenced from taxes_and_totals.js
		// It allows only Sales & Purchase Invoices to calc outstanding amount
		
		// implement total_advance here					
		
		if (!this.frm.doc.write_off_amount)
			this.frm.doc.write_off_amount = 0
		
		frappe.model.round_floats_in(this.frm.doc, ["grand_total"]);
		if(this.frm.doc.party_account_currency == this.frm.doc.currency) {
			var total_amount_to_pay = flt(this.frm.doc.grand_total - this.frm.doc.write_off_amount);
		} else {
			var total_amount_to_pay = flt(flt(this.frm.doc.grand_total*this.frm.doc.conversion_rate, precision("grand_total"))
						- this.frm.doc.write_off_amount, precision("base_grand_total"));							
		}
		
		var paid_amount = (this.frm.doc.party_account_currency == this.frm.doc.currency) ?
				this.frm.doc.paid_amount : this.frm.doc.base_paid_amount;

		var change_amount = (this.frm.doc.party_account_currency == this.frm.doc.currency) ?
			this.frm.doc.change_amount : this.frm.doc.base_change_amount;

		// calculate outstanding amount
		// change_amount is added here
		this.frm.doc.outstanding_amount =  flt(total_amount_to_pay - flt(paid_amount), precision("outstanding_amount"));
		
		// refresh to update it
		this.frm.refresh_fields();
	},

	
	// Debit To
	// --------------------------
	credit_to: function() {
		var me = this;
		if(this.frm.doc.credit_to) {
			me.frm.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Account",
					fieldname: "account_currency",
					filters: { name: me.frm.doc.credit_to },
				},
				callback: function(r, rt) {
					if(r.message) {
						me.frm.set_value("party_account_currency", r.message.account_currency);
						me.set_dynamic_labels();
					}
				}
			});
		}
	},

	
	validate_company_and_party: function() {
		var me = this;
		var valid = true;

		$.each(["company", "supplier"], function(i, fieldname) {			
			if (!me.frm.doc[fieldname]) {
				msgprint(__("Please specify") + ": " +
					frappe.meta.get_label(me.frm.doc.doctype, fieldname, me.frm.doc.name) +
					". " + __("It is needed to fetch Item Details."));
					valid = false;
			}			
		});
		return valid;
	},
	
	// Accounting
	// ---------------------------------------------------------------
	
	
	tax_amount: function() {
			this.calculate_taxes_and_totals();
	},
	
	
	rate: function() {
			this.calculate_taxes_and_totals();
	},
	

	write_off_amount: function() {
		this.set_in_company_currency(this.frm.doc, ["write_off_amount"]);
		this.calculate_outstanding_amount();
		this.frm.refresh_fields();
	},

	paid_amount: function() {
		this.set_in_company_currency(this.frm.doc, ["paid_amount"]);
		this.write_off_amount();
		this.frm.refresh_fields();
	},
	
	
	// To copy Income account and cost center to new row
	// ----------------------------------------------------------------
	items_add: function(doc, cdt, cdn) {
		var row = frappe.get_doc(cdt, cdn);
		this.frm.script_manager.copy_from_first_row("items", row, ["expense_account", "cost_center"]);
	},

	expense_account: function(doc, cdt, cdn) {
		erpnext.utils.copy_value_in_all_row(doc, cdt, cdn, "items", "expense_account");
	},

	cost_center: function(doc, cdt, cdn) {
		erpnext.utils.copy_value_in_all_row(doc, cdt, cdn, "items", "cost_center");
	},
	
	hide_fields(doc) {
		var parent_fields = ['is_opening'];		// fields deleted. compare purchase_invoice.js

		if(cint(doc.is_paid) == 1) {
			hide_field(parent_fields);
		} else {
			for (var i in parent_fields) {
				var docfield = frappe.meta.docfield_map[doc.doctype][parent_fields[i]];
				if(!docfield.hidden) unhide_field(parent_fields[i]);
			}

		}
		
		/*
		var item_fields_stock = ['warehouse_section', 'received_qty', 'rejected_qty'];

		cur_frm.fields_dict['items'].grid.set_column_disp(item_fields_stock,
			(cint(doc.update_stock)==1 || cint(doc.is_return)==1 ? true : false));
		*/
		cur_frm.refresh_fields();
	}
	
});

// ============================s
