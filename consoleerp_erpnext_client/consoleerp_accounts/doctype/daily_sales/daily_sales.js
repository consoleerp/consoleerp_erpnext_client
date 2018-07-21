// Copyright (c) 2018, Console ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on('Daily Sales', {
	refresh: function(frm) {
		if (frm.doc.__islocal) {
			
			// set posting_date = today on new
			frm.set_value("posting_date", frappe.datetime.get_today() || new Date());
			frm.set_value("posting_time", frappe.datetime.now_time() || new Date());
			
			frm.events.fetch_current_employee(frm);
		}
		
		// Cash Bank Account for Debit
		frm.set_query("debit_account", (doc) => {
			return {
				filters: [
					["Account", "account_type", "in", ["Cash", "Bank"]],
					["Account", "root_type", "=", "Asset"],
					["Account", "is_group", "=",0],
					["Account", "company", "=", doc.company]
				]
			}
		});
		frm.events.show_general_ledger(frm);
	},
	
	validate: (frm) => {
		frm.events.calculate_totals(frm);
	},
	
	total_cash_sale: (frm) => {
		frm.events.calculate_totals(frm);
	},
	
	calculate_totals: (frm) => {
		let cash_sales = frm.doc.total_cash_sales || 0;
		let credit_sale = 0;
		(frm.doc.credit_sales || []).forEach((row) => credit_sale += (row.amount || 0));
		let total = cash_sales + credit_sale;
		frm.set_value("total", total);
		frm.set_value("total_credit_sales", credit_sale)
	},
	
	fetch_current_employee: (frm) => {
		frappe.db.get_value("Employee", {user_id: frappe.session.user}, ["name"]).then(r => {
			if (r.message) {
				frappe.model.set_value("Daily Sales", frm.doc.name, "debit_employee", r.message.name);
			}
		});
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

frappe.ui.form.on('Daily Sales Credit Customer', {
	amount: (frm) => {
		frm.events.calculate_totals(frm);
	},
	
	credit_sales_add: (frm) => {
		frm.events.calculate_totals(frm);
	},
	credit_sales_remove: (frm) => {
		frm.events.calculate_totals(frm);
	}
});
