// Copyright (c) 2017, Console ERP and contributors
// For license information, please see license.txt

// Fields to add in the future
// taxes
// advance payments
// write offs
// change amount
// I have mentioned some of the fieldnames in places where they should be included

frappe.provide("consoleerp");
consoleerp.sales_return = erpnext.TransactionController.extend({
	setup: function() {
		
		// defined in StockController.js
		this.setup_posting_date_time_check();
		
		// Debit To
		// ----------------------------
		this.frm.set_query("debit_to", function(doc) {
			// filter on Account
			if (doc.customer) {
				return {
					filters: {
						'account_type': 'Receivable',
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
		
		// Item Query
		// --------------------------------------
		this.frm.set_query("item_code", "items", function() {
			return {
				query: "erpnext.controllers.queries.item_query",
				filters: {'is_sales_item': 1}
			}
		});
		
		
		// Income Account in Details Table
		// --------------------------------------
		this.frm.set_query("income_account", "items", function(doc) {
			return {
				query: "erpnext.controllers.queries.get_income_account",
				filters: {'company': doc.company}
			}
		});
		
		
		// Expense Account
		// ----------------------------
		if (sys_defaults.auto_accounting_for_stock) {
			cur_frm.fields_dict['items'].grid.get_field('expense_account').get_query = function(doc) {
				return {
					filters: {
						'report_type': 'Profit and Loss',
						'company': doc.company,
						"is_group": 0
					}
				}
			}
		}

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
		this._super();
	},
	
	// Override the taxes_and_totals method, call the _super(), 
	// calculate outstanding amount
	calculate_taxes_and_totals: function() {
		
		var me = this;
		var total = 0;

		$.each(this.frm.doc.items, function(i, obj) {
			obj.amount = flt((obj.qty || 0) * (obj.rate || 0), precision('amount', obj))
			obj.net_amount = obj.amount;
			obj.net_rate = obj.rate;
			total += obj.amount;
		});

		this.frm.set_value("total", total);
		
		// discount_amount
		if (this.frm.doc.discount_amount) {
			let discount_amount = this.frm.doc.discount_amount;
			let net_total = total - discount_amount;
			$.each(this.frm.doc.items, function(i, obj) {
				obj.net_amount = flt(obj.amount * net_total / total, precision('net_amount', obj));
				obj.net_rate = flt(obj.net_amount / obj.qty, precision('net_rate', obj));
			});
			this.frm.set_value("net_total", net_total);
		} else {
			this.frm.set_value("net_total", total);
		}
		
		var total_tax = 0;
		$.each(this.frm.doc.taxes, (i, tax) => {
			if (tax.rate) {
				total_tax += flt(tax.rate * this.frm.doc.total / 100, precision("total_taxes_and_charges"));
			}
		});

		this.frm.set_value("total_taxes_and_charges", total_tax);
		this.frm.set_value("grand_total", this.frm.doc.total_taxes_and_charges + this.frm.doc.net_total);
		
		this.set_in_company_currency(this.frm.doc, ["total_taxes_and_charges", "grand_total", "total", "net_total"]);
		
		// refresh to update it
		this.frm.refresh_fields();
	},
		
	
	refresh: function() {

		//
		erpnext.toggle_naming_series();
		erpnext.hide_company();
		
		this.show_general_ledger()
		this.show_stock_ledger()
	},
	
	// Customer
	// --------------------------------------
	customer: function() {
		var me = this;
		if(this.frm.updating_party_details) return;
		
		erpnext.utils.get_party_details(this.frm,
			"erpnext.accounts.party.get_party_details", {
				posting_date: this.frm.doc.posting_date,
				party: this.frm.doc.customer,
				party_type: "Customer",
				account: this.frm.doc.debit_to,
				price_list: this.frm.doc.selling_price_list				
			}, function() {			
			me.apply_pricing_rule();
		})		

		// party account
		// it was supposed to be returned by get_party_details function
		// but it is returned only when doctype = Sales/Purchase Invoice
		frappe.call({
			method: "erpnext.accounts.party.get_party_account",
			args: {
				party_type: 'Customer',
				party: this.frm.doc.customer,
				company: this.frm.doc.company
			},
			callback: function(r) {
				if (r.message)
					me.frm.set_value("debit_to", r.message);
			}
		});
	},
	
	// Is Pos
	// --------------------------------------------------
	is_pos: function(frm){
		this.frm.toggle_reqd("cash_bank_account", this.frm.doc.is_pos);
		if(this.frm.doc.is_pos) {
			if(!this.frm.doc.company) {
				this.frm.set_value("is_pos", 0);
				msgprint(__("Please specify Company to proceed"));
			} else {
				var me = this;
				return this.frm.call({
					doc: me.frm.doc,
					method: "set_missing_values",
					callback: function(r) {
						if(!r.exc) {
							if(r.message && r.message.print_format) {
								frm.pos_print_format = r.message.print_format;
							}
							me.frm.script_manager.trigger("update_stock");
							frappe.model.set_default_values(me.frm.doc);
							me.set_dynamic_labels();
							me.calculate_taxes_and_totals();
						}
					}
				});
			}
		}
		else this.frm.trigger("refresh")
	},

	
	// Debit To
	// --------------------------
	debit_to: function() {
		var me = this;
		if(this.frm.doc.debit_to) {
			me.frm.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Account",
					fieldname: "account_currency",
					filters: { name: me.frm.doc.debit_to },
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

		$.each(["company", "customer"], function(i, fieldname) {
			if(frappe.meta.has_field(me.frm.doc.doctype, fieldname) && me.frm.doc.doctype != "Purchase Order") {
				if (!me.frm.doc[fieldname]) {
					msgprint(__("Please specify") + ": " +
						frappe.meta.get_label(me.frm.doc.doctype, fieldname, me.frm.doc.name) +
						". " + __("It is needed to fetch Item Details."));
						valid = false;
				}
			}
		});
		return valid;
	},
	
	// UOM and Qty
	// -------------------------------
	conversion_factor: function(doc, cdt, cdn, dont_fetch_price_list_rate) {		
		var item = frappe.get_doc(cdt, cdn);
		frappe.model.round_floats_in(item, ["qty", "conversion_factor"]);
		item.stock_qty = flt(item.qty * item.conversion_factor, precision("stock_qty", item));
		refresh_field("stock_qty", item.name, item.parentfield);
		this.toggle_conversion_factor(item);		
	},

	toggle_conversion_factor: function(item) {
		// toggle read only property for conversion factor field if the uom and stock uom are same
		this.frm.fields_dict.items.grid.toggle_enable("conversion_factor",
			(item.uom != item.stock_uom)? true: false)
	},

	qty: function(doc, cdt, cdn) {
		this.conversion_factor(doc, cdt, cdn, true);
		this.apply_pricing_rule(frappe.get_doc(cdt, cdn), true);		
	},
	
	// Accounting
	// ---------------------------------------------------------------
	
	discount_amount: function() {
		this.calculate_taxes_and_totals();
	},
	
	tax_amount: function() {
		this.calculate_taxes_and_totals();
	},
	
	
	rate: function() {
		this.calculate_taxes_and_totals();
	},
	
	
	change_amount: function(){
		if(this.frm.doc.paid_amount > this.frm.doc.grand_total){
			this.calculate_write_off_amount()
		}else {
			this.frm.set_value("change_amount", 0.0)
			this.frm.set_value("base_change_amount", 0.0)
		}

		this.frm.refresh_fields();
	},
	
	
	// To copy Income account and cost center to new row
	// ----------------------------------------------------------------
	items_add: function(doc, cdt, cdn) {
		var row = frappe.get_doc(cdt, cdn);
		this.frm.script_manager.copy_from_first_row("items", row, ["income_account", "cost_center"]);
	},
	
	income_account: function(doc, cdt, cdn) {
		erpnext.utils.copy_value_in_all_row(doc, cdt, cdn, "items", "income_account");
	},

	expense_account: function(doc, cdt, cdn) {
		erpnext.utils.copy_value_in_all_row(doc, cdt, cdn, "items", "expense_account");
	},

	cost_center: function(doc, cdt, cdn) {
		erpnext.utils.copy_value_in_all_row(doc, cdt, cdn, "items", "cost_center");
	},
	
	hide_fields: function(doc) {
		parent_fields = ['project', 'due_date', 'is_opening', 'source', 'total_advance', 'get_advances',
			'advances', 'sales_partner', 'commission_rate', 'total_commission', 'advances', 'from_date', 'to_date'];

		if(cint(doc.is_pos) == 1) {
			hide_field(parent_fields);
		} else {
			for (i in parent_fields) {
				var docfield = frappe.meta.docfield_map[doc.doctype][parent_fields[i]];
				if(!docfield.hidden) unhide_field(parent_fields[i]);
			}
		}

		item_fields_stock = ['batch_no', 'actual_batch_qty', 'actual_qty', 'expense_account',
			'warehouse', 'expense_account', 'quality_inspection']
		this.frm.fields_dict['items'].grid.set_column_disp(item_fields_stock,
			(cint(doc.update_stock)==1 || cint(doc.is_return)==1 ? true : false));

		// India related fields
		if (frappe.boot.sysdefaults.country == 'India') unhide_field(['c_form_applicable', 'c_form_no']);
		else hide_field(['c_form_applicable', 'c_form_no']);

		this.frm.refresh_fields();
	}
	
});


$.extend(cur_frm.cscript, new consoleerp.sales_return({frm: cur_frm}));

// ============================s
