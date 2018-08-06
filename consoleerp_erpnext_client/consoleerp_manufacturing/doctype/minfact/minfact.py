# -*- coding: utf-8 -*-
# Copyright (c) 2018, Console ERP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, erpnext
from frappe.model.document import Document
from erpnext.manufacturing.doctype.bom.bom import validate_bom_no, get_bom_items_as_dict
from erpnext.stock.utils import get_incoming_rate
from erpnext.accounts.general_ledger import process_gl_map
from erpnext.accounts.utils import get_account_currency
from erpnext.stock.get_item_details import get_bin_details, get_default_cost_center, get_conversion_factor
from erpnext.controllers.stock_controller import StockController
from frappe.utils import flt, cint, cstr, nowdate
from erpnext.stock.doctype.stock_entry.stock_entry import get_uom_details
from erpnext.stock import get_warehouse_account_map
from frappe import _

class MinFact(StockController):

	def validate(self):
		
		self.validate_purpose()
		if self.purpose == "Subcontract":
			self.validate_credit_to_acc()
		self.validate_item()
		self.calculate()
		self.update_basic_rates()
	
	def on_submit(self):
		self.update_stock_ledger()
		self.make_gl_entries()
	
	def on_cancel(self):
		self.update_stock_ledger()
		self.make_gl_entries_on_cancel()
	
	def validate_purpose(self):
		if self.purpose not in ["Manufacture", "Subcontract"]:
			frappe.throw("Invalid Purpose")
		
		if self.purpose != "Subcontract":
			self.taxes = []
			self.production_rate = 0
		
	def calculate(self):		
		
		self.total = 0
		if self.apply_rate_on == "Production Qty":
			self.total = flt(self.production_rate * self.qty + self.additional_cost, self.precision("total"))
		elif self.apply_rate_on == "Total Raw Material Qty":
			for item in self.items:
				self.total += (item.qty or 0) * self.production_rate
		
		total_tax = 0
		
		for tax in self.taxes:
			if tax.rate:
				tax_amount = flt(tax.rate * self.total / 100, self.precision("total_taxes_and_charges"))
				tax.tax_amount = tax_amount
				tax.tax_amount_after_discount_amount = tax.tax_amount
				total_tax += tax_amount
				tax.total = self.total + total_tax
				
				self.set_in_company_currency(tax, ["tax_amount", "tax_amount_after_discount_amount"])
		
		self.total_taxes_and_charges = flt(total_tax, self.precision("total_taxes_and_charges"))
		self.grand_total = flt(self.total_taxes_and_charges + self.total, self.precision("grand_total"))
		
		self.set_in_company_currency(self, ["total", "total_taxes_and_charges", "grand_total", "additional_cost"])
	
	def set_in_company_currency(self, doc, fields):
		for f in fields:
			val = flt(flt(doc.get(f), doc.precision(f)) * self.conversion_rate, doc.precision("base_" + f))
			doc.set("base_" + f, val)
	
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
					
	def validate_credit_to_acc(self):
		account = frappe.db.get_value("Account", self.credit_to,
			["account_type", "report_type", "account_currency"], as_dict=True)

		if account.report_type != "Balance Sheet":
			frappe.throw(_("Credit To account must be a Balance Sheet account"))

		if self.supplier and account.account_type != "Payable":
			frappe.throw(_("Credit To account must be a Payable account"))

		self.party_account_currency = account.account_currency
		
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
		
		# rate = raw_material_csot + (supplier cost if subcontracting)
		
		self.rate = flt((total_rm_rate + (self.base_total or 0)) / self.qty, self.precision("rate"))
	
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
		gl_entries = []
		
		self.auto_accounting_for_stock = erpnext.is_perpetual_inventory_enabled(self.company)
		target_warehouse_account = warehouse_account.get(self.warehouse)
		if self.auto_accounting_for_stock:
			self.get_stock_gl_entries(gl_entries, warehouse_account)
		
		if self.purpose == "Subcontract":
			self.make_supplier_gl_entry(gl_entries, target_warehouse_account)
			self.make_tax_gl_entries(gl_entries)
			self.make_payment_gl_entries(gl_entries)
		
		self.make_additional_cost_gl_entry(gl_entries, target_warehouse_account)
		
		print(gl_entries)
		print("FINAL")
		return gl_entries
	
	def get_stock_gl_entries(self, gl_entries, warehouse_account):
		# production_item gl_entry
		# have to specify manually since get_voucher_details iterates through child table only
		sles = self.get_stock_ledger_details()
		prod_sle = sles.get(self.name)[0] # has coc.name when made;
		if not prod_sle.stock_value_difference:
			# updates valuation_Rate, stock_value_difference etc
			prod_sle = self.update_stock_ledger_entries(prod_sle)
		
		if not warehouse_account.get(prod_sle.warehouse):
			frappe.throw("No warehouse account specified for {}".format(prod_sle.warehouse))
		
		against_wacc = []
		for d in self.get('items'):
			sle = sles.get(d.name)[0]
			if not sle.stock_value_difference:
				sle = self.update_stock_ledger_entries(sle)
			
			# raw material warehouses
			gl_entries.append(self.get_gl_dict({
				"account": warehouse_account[sle.warehouse]["account"],
				"against": warehouse_account.get(prod_sle.warehouse)["account"],
				"cost_center": self.cost_center,
				"remarks": self.get("remarks") or "Accounting Entry for Stock",
				"credit": -1 * flt(sle.stock_value_difference, 2), # -1 * since raw material is consumed, stock_value_difference is negative
			}, warehouse_account[sle.warehouse]["account_currency"]))
			
			if sle.warehouse not in against_wacc:
				against_wacc.append(sle.warehouse)

		# to target warehouse
		gl_entries.append(self.get_gl_dict({
			"account": warehouse_account.get(prod_sle.warehouse)["account"],
			"against": ", ".join(against_wacc),
			"cost_center": self.cost_center,
			"remarks": self.get("remarks") or "Accounting Entry for Stock",
			"debit": flt(prod_sle.stock_value_difference, 2)
		}, warehouse_account.get(prod_sle.warehouse)["account_currency"]))
	
	def make_additional_cost_gl_entry(self, gl_entries, target_warehouse_account):
		# additional_cost is given to the manufactured item.
		# so we pass it there		
		additional_cost = flt(self.base_additional_cost, self.precision("base_additional_cost"))
		expenses_included_in_valuation = self.get_company_default("expenses_included_in_valuation")
		if additional_cost:
			gl_entries.append(self.get_gl_dict({
				"account": expenses_included_in_valuation,
				"against": target_warehouse_account['account'],
				"cost_center": self.cost_center,
				"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
				"credit": additional_cost
			}))
	
	def make_supplier_gl_entry(self, gl_entries, target_warehouse_account):
		grand_total = self.grand_total
		# additional costs are entered as part of taxes_and_charges usually
		# here, we simply enter it against Expenses Included in Valuation and Warehouse
		# usually, we have to debit it in expense head
		grand_total -= self.additional_cost
		if grand_total:
			# Didnot use base_grand_total to book rounding loss gle
			grand_total_in_company_currency = flt(grand_total * self.conversion_rate,
				self.precision("grand_total"))
			gl_entries.append(
				self.get_gl_dict({
					"account": self.credit_to,
					"party_type": "Supplier",
					"party": self.supplier,
					"against": target_warehouse_account['account'],
					"credit": grand_total_in_company_currency,
					"credit_in_account_currency": grand_total_in_company_currency \
						if self.party_account_currency == self.company_currency else grand_total,
					"against_voucher": self.name,
					"against_voucher_type": self.doctype,
				}, self.party_account_currency)
			)
			
	def make_tax_gl_entries(self, gl_entries):
		# we dont do these when doing an opeing entry
		# referred from purchase_invoice.py items
	
		# tax table gl entries
		valuation_tax = {}
		for tax in self.get("taxes"):
			if tax.category in ("Total", "Valuation and Total") and flt(tax.base_tax_amount_after_discount_amount):
				account_currency = get_account_currency(tax.account_head)

				dr_or_cr = "debit" if tax.add_deduct_tax == "Add" else "credit"

				gl_entries.append(
					self.get_gl_dict({
						"account": tax.account_head,
						"against": self.supplier,
						dr_or_cr: tax.base_tax_amount_after_discount_amount,
						dr_or_cr + "_in_account_currency": tax.base_tax_amount_after_discount_amount \
							if account_currency==self.company_currency \
							else tax.tax_amount_after_discount_amount,
						"cost_center": tax.cost_center
					}, account_currency)
				)
			# accumulate valuation tax
			if tax.category in ("Valuation", "Valuation and Total") and flt(tax.base_tax_amount_after_discount_amount):
				if self.auto_accounting_for_stock and not tax.cost_center:
					frappe.throw(_("Cost Center is required in row {0} in Taxes table for type {1}").format(tax.idx, _(tax.category)))
				valuation_tax.setdefault(tax.cost_center, 0)
				valuation_tax[tax.cost_center] += \
					(tax.add_deduct_tax == "Add" and 1 or -1) * flt(tax.base_tax_amount_after_discount_amount)

		if self.base_total_taxes_and_charges and valuation_tax:
			# credit valuation tax amount in "Expenses Included In Valuation"
			# this will balance out valuation amount included in cost of goods sold

			total_valuation_amount = sum(valuation_tax.values())
			amount_including_divisional_loss = self.base_total_taxes_and_charges
			i = 1
			for cost_center, amount in valuation_tax.items():
				if i == len(valuation_tax):
					applicable_amount = amount_including_divisional_loss
				else:
					applicable_amount = self.base_total_taxes_and_charges * (amount / total_valuation_amount)
					amount_including_divisional_loss -= applicable_amount

				gl_entries.append(
					self.get_gl_dict({
						"account": self.expenses_included_in_valuation,
						"cost_center": cost_center,
						"against": self.supplier,
						"credit": applicable_amount,
						"remarks": self.remarks or "Accounting Entry for Stock"
					})
				)

				i += 1

		if self.auto_accounting_for_stock and valuation_tax:
			for cost_center, amount in valuation_tax.items():
				gl_entries.append(
					self.get_gl_dict({
						"account": self.expenses_included_in_valuation,
						"cost_center": cost_center,
						"against": self.supplier,
						"credit": amount,
						"remarks": self.remarks or "Accounting Entry for Stock"
					})
				)
	
	def make_payment_gl_entries(self, gl_entries):
		# Make Cash GL Entries
		if cint(self.is_paid) and self.cash_bank_account:
			bank_account_currency = get_account_currency(self.cash_bank_account)
			# CASH, make payment entries
			gl_entries.append(
				self.get_gl_dict({
					"account": self.credit_to,
					"party_type": "Supplier",
					"party": self.supplier,
					"against": self.cash_bank_account,
					"debit": self.base_grand_total,
					"debit_in_account_currency": self.base_grand_total \
						if self.party_account_currency==self.company_currency else self.grand_total,
					"against_voucher": self.name,
					"against_voucher_type": self.doctype,
				}, self.party_account_currency)
			)

			gl_entries.append(
				self.get_gl_dict({
					"account": self.cash_bank_account,
					"against": self.supplier,
					"credit": self.base_grand_total,
					"credit_in_account_currency": self.base_grand_total \
						if bank_account_currency==self.company_currency else self.grand_total
				}, bank_account_currency)
			)
	
	def get_production_item_details(self):
		item_details = self.get_item_details({"item_code": self.production_item})
		print(item_details)
		self.cost_center = item_details.cost_center
		self.expense_account = item_details.expense_account
		return True
	
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