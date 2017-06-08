# -*- coding: utf-8 -*-
# Copyright (c) 2017, Console ERP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, erpnext
from frappe import _
from frappe.utils import flt, cint, cstr
from frappe.model.document import Document
from erpnext.accounts.utils import get_account_currency, get_fiscal_year
from erpnext.accounts.general_ledger import make_gl_entries, merge_similar_entries, delete_gl_entries
from erpnext.accounts.doctype.gl_entry.gl_entry import update_outstanding_amt
from erpnext.controllers.stock_controller import get_warehouse_account
from erpnext.controllers.buying_controller import BuyingController

class PurchaseReturn(BuyingController):
	def validate(self):
		
		if not self.is_opening:
			self.is_opening = ' No'
			
		self.validate_posting_time()
		super(PurchaseReturn, self).validate()
				
		if self.is_paid == 1:
			self.validate_cash()
			
		self.validate_outgoing_rates()
		self.check_conversion_rate()
		self.validate_credit_to_acc()
		self.validate_uom_is_integer("uom", "qty")
		self.set_expense_account(for_validate=True)
		self.set_against_expense_account()
		self.validate_write_off_account()
		self.update_valuation_rate("items")
		self.create_remarks()
		frappe.db.set(self, 'status', 'Draft')
		
		
	def on_submit(self):
		if self.update_stock == 1:
			self.update_stock_ledger()
			from erpnext.stock.doctype.serial_no.serial_no import update_serial_nos_after_submit
			update_serial_nos_after_submit(self, "items")
	
		self.make_gl_entries()
		frappe.db.set(self, 'status', 'Submitted')
		
		
	def on_cancel(self):
		if self.update_stock == 1:
			self.update_stock_ledger()
			
		self.make_gl_entries_on_cancel()
		frappe.db.set(self, 'status', 'Cancelled')
	
	
	def update_stock_ledger(self, allow_negative_stock=False, via_landed_cost_voucher=False):
		self.update_ordered_qty()

		sl_entries = []
		stock_items = self.get_stock_items()

		for d in self.get('items'):
			if d.item_code in stock_items and d.warehouse:
				pr_qty = flt(d.qty) * flt(d.conversion_factor) * -1 				# THIS MAKES THE DIFFERENCE

				if pr_qty:
					sle = self.get_sl_entries(d, {
						"actual_qty": flt(pr_qty),
						"serial_no": cstr(d.serial_no).strip()
					})


					val_rate_db_precision = 6 if cint(d.precision("valuation_rate")) <= 6 else 9
					sle.update({
						"outgoing_rate": flt(d.valuation_rate, val_rate_db_precision)
					})

					sl_entries.append(sle)
				
				"""
				if flt(d.rejected_qty) != 0:
					sl_entries.append(self.get_sl_entries(d, {
						"warehouse": d.rejected_warehouse,
						"actual_qty": flt(d.rejected_qty) * flt(d.conversion_factor),
						"serial_no": cstr(d.rejected_serial_no).strip(),
						"incoming_rate": 0.0
					}))
				"""

		self.make_sl_entries_for_supplier_warehouse(sl_entries)
		self.make_sl_entries(sl_entries, allow_negative_stock=allow_negative_stock,
			via_landed_cost_voucher=via_landed_cost_voucher)
	
	
	def validate_outgoing_rates(self):
		for d in self.get('items'):
			if not d.valuation_rate:
				frappe.throw("Valuation rate is mandatory in Row {0}".format(d.idxs))
	
	
	def make_gl_entries(self, gl_entries=None, repost_future_gle=True, from_repost=False):
		
		self.is_return = 0				# against_voucher thing		
		
		if not self.grand_total:
			return
		if not gl_entries:
			gl_entries = self.get_gl_entries()
		
		if gl_entries:
			update_outstanding = "No" if (cint(self.is_paid) or self.write_off_account) else "Yes"

			make_gl_entries(gl_entries,  cancel=(self.docstatus == 2),
				update_outstanding=update_outstanding, merge_entries=False)

			if update_outstanding == "No":
				update_outstanding_amt(self.credit_to, "Supplier", self.supplier,
					self.doctype, self.return_against if cint(self.is_return) else self.name)

			if repost_future_gle and cint(self.update_stock) and self.auto_accounting_for_stock:
				from erpnext.controllers.stock_controller import update_gl_entries_after
				items, warehouses = self.get_items_and_warehouses()
				update_gl_entries_after(self.posting_date, self.posting_time, warehouses, items)

		elif self.docstatus == 2 and cint(self.update_stock) and self.auto_accounting_for_stock:
			delete_gl_entries(voucher_type=self.doctype, voucher_no=self.name)
	
	
	def get_gl_entries(self, warehouse_account=None):
		self.auto_accounting_for_stock = \
			cint(frappe.defaults.get_global_default("auto_accounting_for_stock"))

		self.stock_received_but_not_billed = self.get_company_default("stock_received_but_not_billed")
		self.expenses_included_in_valuation = self.get_company_default("expenses_included_in_valuation")
		self.negative_expense_to_be_booked = 0.0
		gl_entries = []


		self.make_supplier_gl_entry(gl_entries)		
		self.make_item_gl_entries(gl_entries)
		self.make_tax_gl_entries(gl_entries)		
		
		print(gl_entries)
		gl_entries = merge_similar_entries(gl_entries)
		
		self.make_payment_gl_entries(gl_entries)
		self.make_write_off_gl_entry(gl_entries)

		# process for return
		for gl in gl_entries:
			if gl.debit:
				gl.debit *= -1
				gl.debit_in_account_currency *= -1
			elif gl.credit:
				gl.credit *= -1
				gl.credit_in_account_currency *= -1
		
		return gl_entries
		
		
	def make_supplier_gl_entry(self, gl_entries):
		if self.grand_total:
			# Didnot use base_grand_total to book rounding loss gle
			grand_total_in_company_currency = flt(self.grand_total * self.conversion_rate,
				self.precision("grand_total"))
			gl_entries.append(
				self.get_gl_dict({
					"account": self.credit_to,
					"party_type": "Supplier",
					"party": self.supplier,
					"against": self.against_expense_account,
					"credit": grand_total_in_company_currency,
					"credit_in_account_currency": grand_total_in_company_currency \
						if self.party_account_currency==self.company_currency else self.grand_total,
					"against_voucher": self.name,
					"against_voucher_type": self.doctype,
				}, self.party_account_currency)
			)

	def make_item_gl_entries(self, gl_entries):
		# item gl entries
		stock_items = self.get_stock_items()
		expenses_included_in_valuation = self.get_company_default("expenses_included_in_valuation")
		warehouse_account = get_warehouse_account()

		for item in self.get("items"):
			if flt(item.base_net_amount):
				account_currency = get_account_currency(item.expense_account)

				if self.update_stock and self.auto_accounting_for_stock and item.item_code in stock_items:
					val_rate_db_precision = 6 if cint(item.precision("valuation_rate")) <= 6 else 9

					# warehouse account
					warehouse_debit_amount = flt(flt(item.valuation_rate, val_rate_db_precision)
						* flt(item.qty)	* flt(item.conversion_factor), item.precision("base_net_amount"))
					
					gl_entries.append(
						self.get_gl_dict({
							"account": item.expense_account,
							"against": self.supplier,
							"debit": warehouse_debit_amount,
							"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
							"cost_center": item.cost_center,
							"project": item.project
						}, account_currency)
					)

					# Amount added through landed-cost-voucher
					if flt(item.landed_cost_voucher_amount):
						gl_entries.append(self.get_gl_dict({
							"account": expenses_included_in_valuation,
							"against": item.expense_account,
							"cost_center": item.cost_center,
							"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
							"credit": flt(item.landed_cost_voucher_amount),
							"project": item.project
						}))

					# sub-contracting warehouse
					if flt(item.rm_supp_cost):
						supplier_warehouse_account = warehouse_account[self.supplier_warehouse]["name"]
						gl_entries.append(self.get_gl_dict({
							"account": supplier_warehouse_account,
							"against": item.expense_account,
							"cost_center": item.cost_center,
							"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
							"credit": flt(item.rm_supp_cost)
						}, warehouse_account[self.supplier_warehouse]["account_currency"]))
				else:
					gl_entries.append(
						self.get_gl_dict({
							"account": item.expense_account,
							"against": self.supplier,
							"debit": flt(item.base_net_amount, item.precision("base_net_amount")),
							"debit_in_account_currency": (flt(item.base_net_amount,
								item.precision("base_net_amount")) if account_currency==self.company_currency
								else flt(item.net_amount, item.precision("net_amount"))),
							"cost_center": item.cost_center,
							"project": item.project
						}, account_currency)
					)
			"""
			if self.auto_accounting_for_stock and self.is_opening == "No" and \
				item.item_code in stock_items and item.item_tax_amount:
					# Post reverse entry for Stock-Received-But-Not-Billed if it is booked in Purchase Receipt
					if item.purchase_receipt:
						negative_expense_booked_in_pr = frappe.db.sqlselect name from `tabGL Entry`
							where voucher_type='Purchase Receipt' and voucher_no=%s and account=%s
							(item.purchase_receipt, self.expenses_included_in_valuation))

						if not negative_expense_booked_in_pr:
							gl_entries.append(
								self.get_gl_dict({
									"account": self.stock_received_but_not_billed,
									"against": self.supplier,
									"debit": flt(item.item_tax_amount, item.precision("item_tax_amount")),
									"remarks": self.remarks or "Accounting Entry for Stock"
								})
							)

							self.negative_expense_to_be_booked += flt(item.item_tax_amount, \
								item.precision("item_tax_amount"))
			"""

	def make_tax_gl_entries(self, gl_entries):
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
			if self.is_opening == "No" and tax.category in ("Valuation", "Valuation and Total") and flt(tax.base_tax_amount_after_discount_amount):
				if self.auto_accounting_for_stock and not tax.cost_center:
					frappe.throw(_("Cost Center is required in row {0} in Taxes table for type {1}").format(tax.idx, _(tax.category)))
				valuation_tax.setdefault(tax.cost_center, 0)
				valuation_tax[tax.cost_center] += \
					(tax.add_deduct_tax == "Add" and 1 or -1) * flt(tax.base_tax_amount_after_discount_amount)

		if self.is_opening == "No" and self.negative_expense_to_be_booked and valuation_tax:
			# credit valuation tax amount in "Expenses Included In Valuation"
			# this will balance out valuation amount included in cost of goods sold

			total_valuation_amount = sum(valuation_tax.values())
			amount_including_divisional_loss = self.negative_expense_to_be_booked
			i = 1
			for cost_center, amount in valuation_tax.items():
				if i == len(valuation_tax):
					applicable_amount = amount_including_divisional_loss
				else:
					applicable_amount = self.negative_expense_to_be_booked * (amount / total_valuation_amount)
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

		if self.update_stock and valuation_tax:
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
		if cint(self.is_paid) and self.cash_bank_account and self.paid_amount:
			bank_account_currency = get_account_currency(self.cash_bank_account)
			# CASH, make payment entries
			gl_entries.append(
				self.get_gl_dict({
					"account": self.credit_to,
					"party_type": "Supplier",
					"party": self.supplier,
					"against": self.cash_bank_account,
					"debit": self.base_paid_amount,
					"debit_in_account_currency": self.base_paid_amount \
						if self.party_account_currency==self.company_currency else self.paid_amount,
					"against_voucher": self.name,
					"against_voucher_type": self.doctype,
				}, self.party_account_currency)
			)

			gl_entries.append(
				self.get_gl_dict({
					"account": self.cash_bank_account,
					"against": self.supplier,
					"credit": self.base_paid_amount,
					"credit_in_account_currency": self.base_paid_amount \
						if bank_account_currency==self.company_currency else self.paid_amount
				}, bank_account_currency)
			)

	def make_write_off_gl_entry(self, gl_entries):
		# writeoff account includes petty difference in the invoice amount
		# and the amount that is paid
		if self.write_off_account and flt(self.write_off_amount):
			write_off_account_currency = get_account_currency(self.write_off_account)

			gl_entries.append(
				self.get_gl_dict({
					"account": self.credit_to,
					"party_type": "Supplier",
					"party": self.supplier,
					"against": self.write_off_account,
					"debit": self.base_write_off_amount,
					"debit_in_account_currency": self.base_write_off_amount \
						if self.party_account_currency==self.company_currency else self.write_off_amount,
					"against_voucher": self.name,
					"against_voucher_type": self.doctype,
				}, self.party_account_currency)
			)
			gl_entries.append(
				self.get_gl_dict({
					"account": self.write_off_account,
					"against": self.supplier,
					"credit": flt(self.base_write_off_amount),
					"credit_in_account_currency": self.base_write_off_amount \
						if write_off_account_currency==self.company_currency else self.write_off_amount,
					"cost_center": self.write_off_cost_center
				})
			)
	
	
	def validate_cash(self):
		if not self.cash_bank_account and flt(self.paid_amount):
			frappe.throw(_("Cash or Bank Account is mandatory for making payment entry"))

		if flt(self.paid_amount) + flt(self.write_off_amount) \
				- flt(self.grand_total) > 1/(10**(self.precision("base_grand_total") + 1)):
			frappe.throw(_("""Paid amount + Write Off Amount can not be greater than Grand Total"""))
	
	
	def check_conversion_rate(self):
		default_currency = erpnext.get_company_currency(self.company)
		if not default_currency:
			throw(_('Please enter default currency in Company Master'))
		if (self.currency == default_currency and flt(self.conversion_rate) != 1.00) or not self.conversion_rate or (self.currency != default_currency and flt(self.conversion_rate) == 1.00):
			throw(_("Conversion rate cannot be 0 or 1"))
			
			
	def validate_credit_to_acc(self):
		account = frappe.db.get_value("Account", self.credit_to,
			["account_type", "report_type", "account_currency"], as_dict=True)

		if account.report_type != "Balance Sheet":
			frappe.throw(_("Credit To account must be a Balance Sheet account"))

		if self.supplier and account.account_type != "Payable":
			frappe.throw(_("Credit To account must be a Payable account"))

		self.party_account_currency = account.account_currency
		
		
	def set_expense_account(self, for_validate=False):
		auto_accounting_for_stock = cint(frappe.defaults.get_global_default("auto_accounting_for_stock"))

		if auto_accounting_for_stock:
			stock_not_billed_account = self.get_company_default("stock_received_but_not_billed")
			stock_items = self.get_stock_items()

		if self.update_stock:
			self.validate_item_code()
			self.validate_warehouse()
			warehouse_account = get_warehouse_account()

		for item in self.get("items"):
			# in case of auto inventory accounting,
			# expense account is always "Stock Received But Not Billed" for a stock item
			# except epening entry, drop-ship entry and fixed asset items
						
			if auto_accounting_for_stock and item.item_code in stock_items \
				and self.is_opening == 'No' and not item.is_fixed_asset:

				if self.update_stock:
					item.expense_account = warehouse_account[item.warehouse]["name"]
				else:
					item.expense_account = stock_not_billed_account

			elif not item.expense_account and for_validate:
				throw(_("Expense account is mandatory for item {0}").format(item.item_code or item.item_name))
				
	
	def create_remarks(self):
		if not self.remarks:
			if self.bill_no and self.bill_date:
				self.remarks = _("Against Supplier Invoice {0} dated {1}").format(self.bill_no,
					formatdate(self.bill_date))
			else:
				self.remarks = _("No Remarks")
	
	
	def validate_warehouse(self):
		if self.update_stock:
			for d in self.get('items'):
				if not d.warehouse:
					frappe.throw(_("Warehouse required at Row No {0}").format(d.idx))

		super(PurchaseReturn, self).validate_warehouse()


	def validate_item_code(self):
		for d in self.get('items'):
			if not d.item_code:
				frappe.msgprint(_("Item Code required at Row No {0}").format(d.idx), raise_exception=True)
	
	
	def set_against_expense_account(self):
		against_accounts = []
		for item in self.get("items"):
			if item.expense_account not in against_accounts:
				against_accounts.append(item.expense_account)

		self.against_expense_account = ",".join(against_accounts)
		
		
	def validate_write_off_account(self):
		if self.write_off_amount and not self.write_off_account:
			throw(_("Please enter Write Off Account"))