// Copyright (c) 2016, Console ERP and contributors
// For license information, please see license.txt

frappe.provide("consoleerp.stock");
frappe.provide("erpnext.stock")

frappe.ui.form.on('Warehouse Transfer', {
	setup: function(frm) {
		show_alert("Setup");
		$.extend(frm.cscript, new consoleerp.stock.WarehouseTransfer({frm: frm}));
		
	},
	
	refresh: function(frm) {
		// Receive Items
		if (frm.doc.purpose != "Transfer Receive" && ((frm.doc.docstatus == 1 && frm.doc.status != "Received") || frm.doc.__islocal))
		{			
			// RESEARCH
			// add_custom_button works in refresh only
			cur_frm.add_custom_button(__('Receive Items'), cur_frm.cscript["Receive Items"]);
		}
	},
	
	set_serial_no: function(frm, cdt, cdn) {
		var d = frappe.get_doc(cdt, cdn);
		if (!d.item_code || !d.s_warehouse || !d.transfer_qty) return;
		
		// V8 takes stock_qty instead of qty
		var args = {
			'item_code'		: d.item_code,
			'warehouse'		: d.s_warehouse,
			'qty'			: d.transfer_qty
		};
		frappe.call({
			method: "erpnext.stock.get_item_details.get_serial_no",
			args: {"args": args},
			callback: function(r) {
				console.log(r);
				if (!r.exe) {
					frappe.model.set_value(cdt, cdn, "serial_no", r.message);
				}
			}
		});
	}
});

frappe.ui.form.on("Warehouse Transfer Detail", {
	item_code : function(frm, cdt, cdn) {
		var d = locals[cdt][cdn];		
		
		if (d.item_code) {
			args = {
				'item_code'			: d.item_code,
				'warehouse'			: d.s_warehouse,
				'transfer_qty'		: d.transfer_qty,
				'serial_no'			: d.serial_no,
				'expense_account'	: d.expense_account,
				'cost_center'		: d.cost_center,
				'company'			: frm.doc.company,
				'qty'				: d.qty
			};
			
			return frappe.call({
				doc: frm.doc,
				method: "get_item_details",
				args : args,
				callback: function(r) {
					if (r.message) {
						// WONT WORK IF THIS LINE IS REMOVED (USING d outside the frappe call)
						// RESEARCH
						var d = locals[cdt][cdn];
						$.each(r.message, function(k, v) {
							d[k] = v;
						});
						
						refresh_field("items");
					}
				}
			});
		}
	},
	
	s_warehouse: function(frm, cdt, cdn) {
		frm.events.set_serial_no(frm, cdt, cdn);
	},
	
	uom : function(frm, cdt, cdn) {
		var d = frappe.get_doc(cdt, cdn);
		if (d.uom && d.item_code) {
			return frappe.call({
				method: "consoleerp_erpnext_client.consoleerp_erpnext_client.doctype.warehouse_transfer.warehouse_transfer.get_uom_details",
				args: {
					item_code: d.item_code,
					uom: d.uom,
					qty: d.qty
				},
				callback: function(r) {
					if (r.message) {
						frappe.model.set_value(cdt, cdn, r.message);
					}
				}
			});
		}
	},
	
	expense_account: function(frm, cdt, cdn) {
		// RESEARCH
		erpnext.utils.copy_value_in_all_row(frm.doc, cdt, cdn, "items", "expense_account");
	},
	cost_center: function(frm, cdt, cdn) {
		erpnext.utils.copy_value_in_all_row(frm.doc, cdt, cdn, "items", "cost_center");
	}
});

frappe.ui.form.on('Landed Cost Taxes and Charges', {
	amount: function(frm) {
		// V8 uses frm.events.calculate_amount()
		frm.cscript.calculate_amount();
	}
});

consoleerp.stock.WarehouseTransfer = erpnext.stock.StockController.extend({
	setup : function(){
		
		// V8
		// this.setup_posting_date_time_check();
		
		this.frm.set_query("item_code", "items", function(doc, cdt, cdn) {
			return erpnext.queries.item({is_stock_item: 1});
		});
		
		if (cint(frappe.defaults.get_default("auto_accounting_for_stock"))) {
			this.frm.add_fetch("company", "stock_adjustment_account", "expense_account");
			this.frm.set_query("expense_account", "items", function(doc, cdt, cdn) {
				return {
					filters: {
						"company": me.frm.doc.company,
						"is_group": 0
					}
				}
			});
		}
	},
	
	refresh : function(){			
		
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
		
		// V8
		// adds item frm prev doc based on prev_route()
		// erpnext.utils.add_item(this.frm);
	},
	
	qty: function(doc, cdt, cdn) {
		var d = frappe.get_doc(cdt, cdn);
		d.transfer_qty = flt(d.qty) * flt(d.conversion_factor);
		
		// this has to be done after transfer qty is updated
		this.frm.events.set_serial_no(this.frm, cdt, cdn);
		this.calculate_basic_amount(d);
	},
	
	// on uom change
	// get_stock_details brings in both transfer_qty and conversion_factor
	// hooking event on conversion_factor gives unstable results.. 
	// it gets fired  before the transfer qty is updated..
	// its best to hook it up here on transfer_qty
	transfer_qty: function(doc, cdt, cdn) {
		var d = frappe.get_doc(cdt, cdn);
		this.calculate_basic_amount(d);
	},
	
	calculate_basic_amount: function(item) {
		// calculates row basic amount (without additional rate)
		// item -- row_doc
		// precision() is a function that fetches the precision of a docfield as an int, and flt takes second argument as the same ?? RESEARCH
		item.basic_amount = flt(flt(item.transfer_qty) * flt(item.basic_rate), precision("basic_amount", item));
		this.calculate_amount();
	},
	
	calculate_amount: function() {		
		// this function is to calculate the amount in each row, after distributing the additional_costs to each row
		
		// calc additional costs first
		this.calculate_total_additional_costs();
		
		// total basic amount (amount excluding additional_costs)
		var total_basic_amount = frappe.utils.sum(
			(this.frm.doc.items || []).map(function(x) { return x.basic_amount; })
		);
		for (var i in this.frm.doc.items) {
			var item = this.frm.doc.items[i];
			
			item.additional_cost = (flt(item.basic_amount) / total_basic_amount) * this.frm.doc.total_additional_costs;
			
			item.amount = flt(item.basic_amount + flt(item.additional_cost),
					precision("amount", item))
			
			item.valuation_rate = flt(flt(item.basic_rate)
					+ (flt(item.additional_cost) / flt(item.transfer_qty)),
					precision("valuation_rate", item));
		}
		
		refresh_field("items");
	},
	
	calculate_total_additional_costs: function() {
		// sum everything
		var total_additional_costs = frappe.utils.sum(
			(this.frm.doc.additional_costs || []).map(function(c) { return flt(c.amount); })
		);
		
		// set_value with precision
		this.frm.set_value("total_additional_costs", flt(total_additional_costs, precision("total_additional_costs")));
	},
	
	
	// update in the detail
	items_add: function(doc, cdt, cdn) {
		// try the same with the given doc variable.. did not work on the first try.. RESEARCH
		var row = frappe.get_doc(cdt, cdn);
		this.frm.script_manager.copy_from_first_row("items", row, ["expense_account", "cost_center"])
		
		row.s_warehouse = this.frm.doc.from_warehouse;
		row.t_warehouse = this.frm.doc.to_warehouse;		
	},
	
	basic_rate : function(doc, cdt, cdn) {
		var item = frappe.get_doc(cdt, cdn);
		this.calculate_basic_amount(item);
	},
	
	from_warehouse: function(doc) {
		this.set_warehouse_if_different("s_warehouse", doc.from_warehouse);
	},
	
	to_warehouse: function(doc) {
		this.set_warehouse_if_different("t_warehouse", doc.to_warehouse);
	},
	
	// RESEARCH
	// cur_frm.open_grid_row() -- gets the open row
	items_on_form_rendered: function(doc, grid_row) {
		erpnext.setup_serial_no();
	},
	
	set_warehouse_if_different: function(fieldname, value) {
		for (var i = 0, l = (this.frm.doc.items || []).length; i<l; i++) {
			var row = this.frm.doc.items[i];
			if (row[fieldname] != value) {				
				frappe.model.set_value(row.doctype, row.name, fieldname, value, "link");
			}
		}
	},
	
	onload_post_render: function() {
		var me = this;
		this.set_default_account(function() {
			if (me.frm.doc.__islocal && me.frm.doc.company && !me.frm.doc.amended_from) {
				// RESEARCH
				me.frm.trigger("company");
			}
		});
	},
	
	set_default_account: function(callback) {
		var me = this;
		
		if (cint(frappe.defaults.get_default("auto_accounting_for_stock")) && this.frm.doc.company) {
			return this.frm.call({
				method: "erpnext.accounts.utils.get_company_default",
				args: {
					fieldname: "stock_adjustment_account",
					company: this.frm.doc.company
				},
				callback: function(r) {
					if (!r.exc) {
						$.each(me.frm.doc.items || [], function(i, d) {
							if (!d.expense_account)
								d.expense_account = r.message;
						});
						if (callback) callback();
					}
				}
			});
		}
	},
		
	// when detail source warehouse is changed
	s_warehouse: function(doc, cdt, cdn) {
		this.get_warehouse_details(doc, cdt, cdn);
	},
	
	get_warehouse_details: function(doc, cdt, cdn) {
		// referenced from stock_entry.js
		// bom check-- here
		var me = this;
		var d = locals[cdt][cdn];
		frappe.call({
			method: "erpnext.stock.doctype.stock_entry.stock_entry.get_warehouse_details",
			args : {
				"args" : {
					"item_code" 	: d.item_code,
					"warehouse" 	: d.s_warehouse,
					"transfer_qty" 	: d.transfer_qty,
					"qty"			: -1 * d.qty, // refer the same in stock_entry.js
					"posting_date"	: this.frm.doc.posting_date,
					"posting_time"	: this.frm.doc.posting_time
				}
			},
			callback: function(r){
				if (!r.exc) {
					$.extend(d, r.message);
					me.calculate_basic_amount(d)
				}
			}
		});
	}
});

cur_frm.cscript["Receive Items"] = function() {
	
	if (cur_frm.doc.docstatus == 1) { // IF SUBMITTED
		// RESEARCH
		frappe.model.open_mapped_doc({
			method: "consoleerp_erpnext_client.consoleerp_erpnext_client.doctype.warehouse_transfer.warehouse_transfer.receive_items",
			frm: cur_frm
		});
	} else {
		// LOCAL
		show_alert("S");
		erpnext.utils.map_current_doc({
			method: "consoleerp_erpnext_client.consoleerp_erpnext_client.doctype.warehouse_transfer.warehouse_transfer.receive_items",
			source_doctype: "Warehouse Transfer",
			get_query_filters: {
				docstatus: 1,
				purpose: ["=", "Transfer Issue"],
				status: ["=", "Issued"],
				company: cur_frm.doc.company
			}
		});
	}
}