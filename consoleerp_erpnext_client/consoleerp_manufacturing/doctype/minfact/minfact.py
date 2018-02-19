# -*- coding: utf-8 -*-
# Copyright (c) 2018, Console ERP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from erpnext.manufacturing.doctype.bom.bom import validate_bom_no, get_bom_items_as_dict
from erpnext.stock.utils import get_incoming_rate
from erpnext.accounts.general_ledger import process_gl_map
from erpnext.stock.get_item_details import get_bin_details, get_default_cost_center, get_conversion_factor
from erpnext.controllers.stock_controller import StockController
from frappe.utils import flt, cint, cstr, nowdate
from erpnext.stock.doctype.stock_entry.stock_entry import get_uom_details
from erpnext.stock import get_warehouse_account_map
from frappe import _

class MinFact(StockController):

	def validate(self):
		
		self.validate_item()
		self.update_basic_rates()
	
	def on_submit(self):
		self.update_stock_ledger()
		self.make_gl_entries()
	
	def on_cancel(self):
		self.update_stock_ledger()
		self.make_gl_entries_on_cancel()
		
	def validate_item(self):
		stock_items = self.get_stock_items()
		serialized_items = self.get_serialized_items()
		for item in self.get("items"):
			if item.item_code not in stock_items:
				frappe.throw(_("{0} is not a stock Item").format(item.item_code))

			item_details = self.get_item_details(frappe._dict(
				{"item_code": item.item_code, "company": self.company,
				"uom": item.uom, 's_warehouse': item.warehouse}),
				for_update=True)

			for f in ("uom", "stock_uom", "description", "item_name", "expense_account",
				"cost_center", "conversion_factor"):
					if f in ["stock_uom", "conversion_factor"] or not item.get(f):
						item.set(f, item_details.get(f))

			item.stock_qty = item.qty * item.conversion_factor

			if not item.serial_no and item.item_code in serialized_items:
				frappe.throw(_("Row #{0}: Please specify Serial No for Item {1}").format(item.idx, item.item_code),
					frappe.MandatoryError)
		
	def update_basic_rates(self):
		total_rm_rate = 0
		for rm in self.items:
			rm.basic_rate = flt(
								get_incoming_rate({
									"item_code": rm.item_code,
									"warehouse": rm.warehouse,
									"posting_date": self.posting_date,
									"posting_time": self.posting_time,
									"qty": -1*flt(rm.stock_qty),
									"serial_no": rm.serial_no,
									"voucher_type": self.doctype,
									"voucher_no": rm.name,
									"company": self.company,
									"allow_zero_valuation": rm.allow_zero_valuation_rate
								}), # raise_error_if_no_rate
								self.precision("basic_rate", rm))
			rm.basic_amount = flt(rm.basic_rate * rm.stock_qty, self.precision("basic_amount", rm))
			total_rm_rate += rm.basic_amount
		
		self.rate = flt((total_rm_rate + self.additional_cost) / self.qty, self.precision("rate"))
	
	def get_items_from_bom(self):
		self.items = []
		if self.bom_no and self.qty:
			item_dict = get_bom_items_as_dict(self.bom_no, self.company, qty=self.qty,
				fetch_exploded = 1)
			
			for item in sorted(item_dict.values(), key=lambda d: d['idx']):
					self.append('items', {
						'item_code': item.item_code,
						'item_name': item.item_name,
						'description': item.description,
						'qty': item.qty,
						'conversion_factor': 1,
						'stock_qty': item.qty,
						'uom': item.stock_uom
					})
		return True
		
	def update_stock_ledger(self):
		sl_entries = []

		for d in self.get('items'):
			sl_entries.append(self.get_sl_entries(d, {
				"warehouse": cstr(d.warehouse),
				"actual_qty": -flt(d.stock_qty),
				"incoming_rate": 0
			}))

		# manufacturing item
		sl_entries.append(self.get_sl_entries(self, {
			"item_code": cstr(self.production_item),
			"warehouse": cstr(self.warehouse),
			"actual_qty": flt(self.qty),
			"batch_no": cstr(self.batch_no).strip(),
			"incoming_rate": self.rate
		}));	
		
		if self.docstatus == 2:
			sl_entries.reverse()

		self.make_sl_entries(sl_entries, self.amended_from and 'Yes' or 'No')
	
	def get_gl_entries(self, warehouse_account):
		expenses_included_in_valuation = self.get_company_default("expenses_included_in_valuation")
		gl_entries = super(MinFact, self).get_gl_entries(warehouse_account)

		# production_item gl_entry
		# have to specify manually since get_voucher_details iterates through child table only
		prod_sle = self.get_stock_ledger_details().get(self.name)[0]
		if not prod_sle.stock_value_difference and not item_row.get("allow_zero_valuation_rate"):
			# updates valuation_Rate, stock_value_difference etc
			prod_sle = self.update_stock_ledger_entries(prod_sle)
		
		warehouse_account = get_warehouse_account_map()
		if not warehouse_account.get(prod_sle.warehouse):
			frappe.throw("No warehouse account specified for {}".format(prod_sle.warehouse))
		# to warehouse account
		gl_entries.append(self.get_gl_dict({
			"account": warehouse_account[prod_sle.warehouse]["account"],
			"against": self.expense_account,
			"cost_center": self.cost_center,
			"remarks": self.get("remarks") or "Accounting Entry for Stock",
			"debit": flt(prod_sle.stock_value_difference, 2),
		}, warehouse_account[prod_sle.warehouse]["account_currency"]))

		# to expense account (Cost of Goods Sold)
		gl_entries.append(self.get_gl_dict({
			"account": self.expense_account,
			"against": warehouse_account[prod_sle.warehouse]["account"],
			"cost_center": self.cost_center,
			"remarks": self.get("remarks") or "Accounting Entry for Stock",
			"credit": flt(prod_sle.stock_value_difference, 2),
			"project": self.get("project") or self.get("project")
		}))
		
		# additional_cost is given to the manufactured item.
		# so we pass it there		
		additional_cost = flt(self.additional_cost, self.precision("additional_cost"))
		if additional_cost:
			gl_entries.append(self.get_gl_dict({
				"account": expenses_included_in_valuation,
				"against": self.expense_account,
				"cost_center": self.cost_center,
				"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
				"credit": additional_cost
			}))

			gl_entries.append(self.get_gl_dict({
				"account": self.expense_account,
				"against": expenses_included_in_valuation,
				"cost_center": self.cost_center,
				"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
				"credit": -1 * additional_cost # put it as negative credit instead of debit purposefully
			}))
			
		return gl_entries
	
	def get_item_details(self, args=None, for_update=False):
		item = frappe.db.sql("""select stock_uom, description, image, item_name,
				expense_account, buying_cost_center, item_group, has_serial_no,
				has_batch_no, sample_quantity
			from `tabItem`
			where name = %s
				and disabled=0
				and (end_of_life is null or end_of_life='0000-00-00' or end_of_life > %s)""",
			(args.get('item_code'), nowdate()), as_dict = 1)
		if not item:
			frappe.throw(_("Item {0} is not active or end of life has been reached").format(args.get("item_code")))

		item = item[0]

		ret = frappe._dict({
			'uom'			      	: item.stock_uom,
			'stock_uom'			  	: item.stock_uom,
			'description'		  	: item.description,
			'image'					: item.image,
			'item_name' 		  	: item.item_name,
			'expense_account'		: args.get("expense_account"),
			'cost_center'			: get_default_cost_center(args, item),
			'qty'					: 0,
			'stock_qty'				: 0,
			'conversion_factor'		: 1,
			'batch_no'				: '',
			'actual_qty'			: 0,
			'basic_rate'			: 0,
			'serial_no'				: '',
			'has_serial_no'			: item.has_serial_no,
			'has_batch_no'			: item.has_batch_no,
			'sample_quantity'		: item.sample_quantity
		})
		for d in [["Account", "expense_account", "default_expense_account"],
			["Cost Center", "cost_center", "cost_center"]]:
				company = frappe.db.get_value(d[0], ret.get(d[1]), "company")
				if not ret[d[1]] or (company and self.company != company):
					ret[d[1]] = frappe.db.get_value("Company", self.company, d[2]) if d[2] else None

		# update uom
		if args.get("uom") and for_update:
			ret.update(get_uom_details(args.get('item_code'), args.get('uom'), args.get('qty')))

		if not ret["expense_account"]:
			ret["expense_account"] = frappe.db.get_value("Company", self.company, "stock_adjustment_account")

		args['posting_date'] = self.posting_date
		args['posting_time'] = self.posting_time

		stock_and_rate = get_warehouse_details(args) if args.get('warehouse') else {}
		ret.update(stock_and_rate)

		# automatically select batch for outgoing item
		if (args.get('warehouse', None) and args.get('qty') and
			ret.get('has_batch_no') and not args.get('batch_no')):
			args.batch_no = get_batch_no(args['item_code'], args['warehouse'], args['qty'])

		return ret