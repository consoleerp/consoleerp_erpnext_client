# -*- coding: utf-8 -*-
# Copyright (c) 2017, Console ERP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint, flt, cstr
from erpnext.accounts.party import get_party_account, get_due_date
from erpnext.controllers.stock_controller import update_gl_entries_after
from erpnext.accounts.utils import get_account_currency
from erpnext.accounts.doctype.sales_invoice.pos import update_multi_mode_option
from frappe.model.document import Document
from erpnext.controllers.stock_controller import StockController

class SalesReturn(StockController):
	
	"""
	get_incoming_rate_for_sales_return
	This method was overriden to provide current valuation_rate as incoming rate
	"""
	
	def validate(self):

		self.validate_posting_time()										# auto sets posting date and time to now		
		self.validate_uom_is_integer("stock_uom", "qty")					# checks for whole number UOMs and verify the qtys	# TransactionBase
		self.validate_debit_to_acc()										# debit_to validation
		
		self.validate_income_rates()
		
		if cint(self.is_pos):
			self.validate_pos()		

		self.set_against_income_account()
		
		self.add_remarks()
		self.validate_item_code()						# simply checks if item code is present
		self.validate_warehouse()						# checks if warehouse is present for stock item
		self.update_current_stock()
		
		self.update_packing_list()
		frappe.db.set(self, 'status', 'Draft')
		
		self.calculate_taxes_and_totals()
	
	def on_submit(self):
		
		self.fake_return_for_stock_ledger(1)
		self.update_stock_ledger()				# always update_stock
		self.fake_return_for_stock_ledger(0)
		
		self.make_gl_entries()
		frappe.db.set(self, 'status', 'Submitted')
	
	def on_cancel(self):
		self.fake_return_for_stock_ledger(1)
		self.update_stock_ledger()
		self.fake_return_for_stock_ledger(0)

		self.make_gl_entries_on_cancel()
		frappe.db.set(self, 'status', 'Cancelled')
		
	
	def calculate_taxes_and_totals(self):
		total = 0;
		
		for item in self.items:
			item.amount = flt(item.rate * item.qty, self.precision("amount", item))
			item.net_amount = item.amount
			item.net_rate = item.rate
			total += item.amount
			
			self._set_in_company_currency(item, ['amount', 'rate', 'net_amount', 'net_rate'])
	
		self.total = total
		
		# only supports discount amount for now
		if self.discount_amount:
			net_total = total - self.discount_amount
			for item in self.items:
				item.net_amount = flt(item.amount * net_total / total, self.precision('net_amount', item))
				item.net_rate = flt(item.net_amount / item.qty, self.precision('net_rate', item))
				self._set_in_company_currency(item, ['net_amount', 'net_rate'])
			
			self.net_total = net_total
		else:
			self.net_total = total
			
		# taxes
		total_tax = 0
		for tax in self.taxes:
			if tax.rate:
				tax_amount = flt(tax.rate * self.total / 100, self.precision("total_taxes_and_charges"))
				tax.tax_amount = tax_amount
				tax.tax_amount_after_discount_amount = tax.tax_amount
				total_tax += tax_amount
				tax.total = self.total + total_tax
				
				self._set_in_company_currency(tax, ["tax_amount", "tax_amount_after_discount_amount"])
		
		self.total_taxes_and_charges = flt(total_tax, self.precision("total_taxes_and_charges"))
		self.grand_total = flt(self.total_taxes_and_charges + self.net_total, self.precision("grand_total"))
		
		self._set_in_company_currency(self, ["total", "total_taxes_and_charges", "grand_total", "net_total"])
		
		from frappe.utils import money_in_words
		self.in_words = money_in_words(self.grand_total, self.currency)
		
	def _set_in_company_currency(self, doc, fields):
		"""set values in base currency"""
		for f in fields:
			val = flt(flt(doc.get(f), doc.precision(f)) * self.conversion_rate, doc.precision("base_" + f))
			doc.set("base_" + f, val)
	
	def update_stock_ledger(self):

		sl_entries = []
		for d in self.get_item_list():
			if frappe.db.get_value("Item", d.item_code, "is_stock_item") == 1 and flt(d.qty):
				if flt(d.conversion_factor)==0.0:
					d.conversion_factor = get_conversion_factor(d.item_code, d.uom).get("conversion_factor") or 1.0
				return_rate = 0
				if cint(self.is_return) and self.return_against and self.docstatus==1:
					return_rate = self.get_incoming_rate_for_sales_return(d.item_code, self.return_against)

				# On cancellation or if return entry submission, make stock ledger entry for
				# target warehouse first, to update serial no values properly

				if d.warehouse and ((not cint(self.is_return) and self.docstatus==1)
					or (cint(self.is_return) and self.docstatus==2)):
						sl_entries.append(self.get_sl_entries(d, {
							"actual_qty": -1*flt(d.qty),
							"incoming_rate": return_rate
						}))

				if d.target_warehouse:
					target_warehouse_sle = self.get_sl_entries(d, {
						"actual_qty": flt(d.qty),
						"warehouse": d.target_warehouse
					})

					if self.docstatus == 1:
						if not cint(self.is_return):
							args = frappe._dict({
								"item_code": d.item_code,
								"warehouse": d.warehouse,
								"posting_date": self.posting_date,
								"posting_time": self.posting_time,
								"qty": -1*flt(d.qty),
								"serial_no": d.serial_no,
								"company": d.company,
								"voucher_type": d.voucher_type,
								"voucher_no": d.name,
								"allow_zero_valuation": d.allow_zero_valuation
							})
							target_warehouse_sle.update({
								"incoming_rate": get_incoming_rate(args)
							})
						else:
							target_warehouse_sle.update({
								"outgoing_rate": return_rate
							})
					sl_entries.append(target_warehouse_sle)

				if d.warehouse and ((not cint(self.is_return) and self.docstatus==2)
					or (cint(self.is_return) and self.docstatus==1)):
						sl_entries.append(self.get_sl_entries(d, {
							"actual_qty": -1*flt(d.qty),
							"incoming_rate": return_rate
						}))
		self.make_sl_entries(sl_entries)
	
	def fake_return_for_stock_ledger(self, fake):
		self.is_return = fake
		self.return_against = "some-doc" if fake else None
		for d in self.get('items'):			
			d.stock_qty *= -1
			d.so_detail = None
					
			
		for d in self.get('packed_items'):
			d.qty *= -1
	
	# OVERRIDEN METHOD
	# GET ANY STOCK LEDGER ENTRY AND DO STOCK_VALUE_DIFF / ACTUAL QTY = RATE
	def get_incoming_rate_for_sales_return(self, item_code, against_document):
		""" 
		We dont have much control here regarding from which warehouse
			- check for item_code warehouse combination and get rate
			- get any warehouse rate if not present
		"""
		incoming_rate = 0.0
		
		if not item_code:
			return 0
		
		# check in packed items too
		doc = filter(lambda x: x.item_code == item_code, self.get('items') + self.get('packed_items'))[0]
				
		incoming_rate = frappe.db.sql("""select abs(stock_value_difference / actual_qty)
			from `tabStock Ledger Entry`
			where item_code = %s and warehouse = %s and posting_date < %s
			order by posting_date desc limit 1""",
			(item_code, doc.warehouse, self.posting_date))
		incoming_rate = incoming_rate[0][0] if incoming_rate else doc.valuation_rate
		

		return incoming_rate
	
	
	def validate_income_rates(self):
		for d in self.get('items'):
			if self.has_product_bundle(d.item_code):
				for p in self.get("packed_items"):
					if p.parent_detail_docname == d.name and p.parent_item == d.item_code:
						incoming_rate = frappe.db.sql("""select abs(stock_value_difference / actual_qty)
							from `tabStock Ledger Entry`
							where item_code = %s and warehouse = %s
							order by posting_date desc limit 1""",
							(p.item_code, p.warehouse))
						incoming_rate = incoming_rate[0][0] if incoming_rate else 0
						if not incoming_rate:				
							frappe.throw(_("Packing List Item ({0}) not found in Warehouse {1} under Packing List {2}".format(p.item_code, p.warehouse, d.item_code)))
			else:
				incoming_rate = frappe.db.sql("""select abs(stock_value_difference / actual_qty)
					from `tabStock Ledger Entry`
					where item_code = %s and warehouse = %s
					order by posting_date desc limit 1""",
					(d.item_code, d.warehouse))
				incoming_rate = incoming_rate[0][0] if incoming_rate else d.valuation_rate
				if not incoming_rate:				
					frappe.throw(_("Valuation Rate is mandatory for Row {0}".format(d.idx)))
	
	
	# Write Off
	"""
	def validate_write_off_account(self):
		if flt(self.write_off_amount) and not self.write_off_account:
			self.write_off_account = frappe.db.get_value('Company', self.company, 'write_off_account')

		if flt(self.write_off_amount) and not self.write_off_account:
			msgprint(_("Please enter Write Off Account"), raise_exception=1)
	
	
	def validate_account_for_change_amount(self):
		if flt(self.change_amount) and not self.account_for_change_amount:
			msgprint(_("Please enter Account for Change Amount"), raise_exception=1)
	"""
	
	def set_against_income_account(self):
		"""Set against account for debit to account"""
		against_acc = []
		for d in self.get('items'):
			if d.income_account not in against_acc:
				against_acc.append(d.income_account)
		self.against_income_account = ','.join(against_acc)
	
	
	def clear_unallocated_mode_of_payments(self):
		self.set("payments", self.get("payments", {"amount": ["not in", [0, None, ""]]}))

		frappe.db.sql("""delete from `tabSales Invoice Payment` where parent = %s
			and amount = 0""", self.name)

			
	def validate_pos(self):	
		if not self.cash_bank_account:
			frappe.throw("Cash Bank Account is necessary")
				
	def validate_item_code(self):
		for d in self.get('items'):
			if not d.item_code:
				msgprint(_("Item Code required at Row No {0}").format(d.idx), raise_exception=True)
			
			
	def validate_warehouse(self):
		super(SalesReturn, self).validate_warehouse()

		for d in self.get_item_list():
			if not d.warehouse and frappe.db.get_value("Item", d.item_code, "is_stock_item"):
				frappe.throw(_("Warehouse required for stock Item {0}").format(d.item_code))
		
		
	def update_current_stock(self):
		for d in self.get('items'):
			if d.item_code and d.warehouse:
				bin = frappe.db.sql("select actual_qty from `tabBin` where item_code = %s and warehouse = %s", (d.item_code, d.warehouse), as_dict = 1)
				d.actual_qty = bin and flt(bin[0]['actual_qty']) or 0

		for d in self.get('packed_items'):
			bin = frappe.db.sql("select actual_qty, projected_qty from `tabBin` where item_code =	%s and warehouse = %s", (d.item_code, d.warehouse), as_dict = 1)
			d.actual_qty = bin and flt(bin[0]['actual_qty']) or 0
			d.projected_qty = bin and flt(bin[0]['projected_qty']) or 0
	
	
	def add_remarks(self):
		if not self.remarks: self.remarks = 'No Remarks'
	
	
	def get_item_list(self):
		il = []
		for d in self.get("items"):
			if d.qty is None:
				frappe.throw(_("Row {0}: Qty is mandatory").format(d.idx))

			if self.has_product_bundle(d.item_code):
				for p in self.get("packed_items"):
					if p.parent_detail_docname == d.name and p.parent_item == d.item_code:
						# the packing details table's qty is already multiplied with parent's qty
						il.append(frappe._dict({
							'warehouse': p.warehouse or d.warehouse,
							'item_code': p.item_code,
							'qty': flt(p.qty),
							'uom': p.uom,
							'batch_no': cstr(p.batch_no).strip(),
							'serial_no': cstr(p.serial_no).strip(),
							'name': d.name,
							'target_warehouse': p.target_warehouse,
							'company': self.company,
							'voucher_type': self.doctype,
							'allow_zero_valuation': 0 # d.allow_zero_valuation_rate
						}))
			else:
				il.append(frappe._dict({
					'warehouse': d.warehouse,
					'item_code': d.item_code,
					'qty': d.stock_qty,
					'uom': d.uom,
					'stock_uom': d.stock_uom,
					'conversion_factor': d.conversion_factor,
					'batch_no': cstr(d.get("batch_no")).strip(),
					'serial_no': cstr(d.get("serial_no")).strip(),
					'name': d.name,
					'target_warehouse': d.target_warehouse,
					'company': self.company,
					'voucher_type': self.doctype,
					'allow_zero_valuation': 0 # d.allow_zero_valuation_rate
				}))
		return il
	
	def update_packing_list(self):		
		from erpnext.stock.doctype.packed_item.packed_item import make_packing_list
		make_packing_list(self)
	
	def has_product_bundle(self, item_code):
		return frappe.db.sql("""select name from `tabProduct Bundle`
			where new_item_code=%s and docstatus != 2""", item_code)
	
	def validate_debit_to_acc(self):
		account = frappe.db.get_value("Account", self.debit_to,
			["account_type", "report_type", "account_currency"], as_dict=True)

		if not account:
			frappe.throw(_("Debit To is required"))

		if account.report_type != "Balance Sheet":
			frappe.throw(_("Debit To account must be a Balance Sheet account"))

		if self.customer and account.account_type != "Receivable":
			frappe.throw(_("Debit To account must be a Receivable account"))

		self.party_account_currency = account.account_currency
	
	
	# sales_invoice.py
	def set_missing_values(self, for_validate=False):
		if not self.debit_to:
			self.debit_to = get_party_account("Customer", self.customer, self.company)
		
		
	def make_gl_entries(self, gl_entries=None, repost_future_gle=True, from_repost=False):
		if not self.grand_total:
			return

		if not gl_entries:
			gl_entries = self.get_gl_entries()

		if gl_entries:
			from erpnext.accounts.general_ledger import make_gl_entries

			# if POS and amount is written off, updating outstanding amt after posting all gl entries
			update_outstanding = "No" if (cint(self.is_pos)) else "Yes"
			import json
			print("GLLIST JSON:")
			# print(json.dumps(gl_entries))
			make_gl_entries(gl_entries, cancel=(self.docstatus == 2),
				update_outstanding=update_outstanding, merge_entries=False)

			if update_outstanding == "No":
				
				from erpnext.accounts.doctype.gl_entry.gl_entry import update_outstanding_amt
				update_outstanding_amt(self.debit_to, "Customer", self.customer,
					self.doctype, self.name)

			if repost_future_gle and cint(self.update_stock) \
				and cint(frappe.defaults.get_global_default("auto_accounting_for_stock")):
					items, warehouses = self.get_items_and_warehouses()
					update_gl_entries_after(self.posting_date, self.posting_time, warehouses, items)
		elif self.docstatus == 2 and cint(self.update_stock) \
			and cint(frappe.defaults.get_global_default("auto_accounting_for_stock")):
				from erpnext.accounts.general_ledger import delete_gl_entries
				delete_gl_entries(voucher_type=self.doctype, voucher_no=self.name)
	
	
	def get_gl_entries(self, warehouse_account=None):
		from erpnext.accounts.general_ledger import merge_similar_entries

		gl_entries = []

		self.make_customer_gl_entry(gl_entries)
		
		self.make_tax_gl_entries(gl_entries)

		self.make_item_gl_entries(gl_entries)

		# merge gl entries before adding pos entries
		gl_entries = merge_similar_entries(gl_entries)

		self.make_pos_gl_entries(gl_entries)
				
		# self.make_gle_for_change_amount(gl_entries)

		# self.make_write_off_gl_entry(gl_entries)

		# process for return
		for gl in gl_entries:
			if gl.debit:
				gl.debit *= -1
				gl.debit_in_account_currency *= -1
			elif gl.credit:
				gl.credit *= -1
				gl.credit_in_account_currency *= -1
				
		
		return gl_entries
		
	
	def make_customer_gl_entry(self, gl_entries):
		if self.grand_total:
			# Didnot use base_grand_total to book rounding loss gle
			grand_total_in_company_currency = flt(self.grand_total * self.conversion_rate,
				self.precision("grand_total"))

			gl_entries.append(
				self.get_gl_dict({
					"account": self.debit_to,
					"party_type": "Customer",
					"party": self.customer,
					"against": self.against_income_account,
					"debit": grand_total_in_company_currency,
					"debit_in_account_currency": grand_total_in_company_currency \
						if self.party_account_currency==self.company_currency else self.grand_total,
					"against_voucher": self.name,
					"against_voucher_type": self.doctype
				}, self.party_account_currency)
			)
			
	
	def make_tax_gl_entries(self, gl_entries):
		for tax in self.get("taxes"):
			if flt(tax.base_tax_amount_after_discount_amount):
				account_currency = get_account_currency(tax.account_head)
				gl_entries.append(
					self.get_gl_dict({
						"account": tax.account_head,
						"against": self.customer,
						"credit": flt(tax.base_tax_amount_after_discount_amount),
						"credit_in_account_currency": flt(tax.base_tax_amount_after_discount_amount) \
							if account_currency==self.company_currency else flt(tax.tax_amount_after_discount_amount),
						"cost_center": tax.cost_center
					}, account_currency)
				)
				
			
	def make_item_gl_entries(self, gl_entries):
		# income account gl entries
		for item in self.get("items"):
			if flt(item.base_net_amount):
				if item.is_fixed_asset:
					asset = frappe.get_doc("Asset", item.asset)

					fixed_asset_gl_entries = get_gl_entries_on_asset_disposal(asset, item.base_net_amount)
					for gle in fixed_asset_gl_entries:
						gle["against"] = self.customer
						gl_entries.append(self.get_gl_dict(gle))

					asset.db_set("disposal_date", self.posting_date)
					asset.set_status("Sold" if self.docstatus==1 else None)
				else:
					account_currency = get_account_currency(item.income_account)
					gl_entries.append(
						self.get_gl_dict({
							"account": item.income_account,
							"against": self.customer,
							"credit": item.base_net_amount,
							"credit_in_account_currency": item.base_net_amount \
								if account_currency==self.company_currency else item.net_amount,
							"cost_center": item.cost_center
						}, account_currency)
					)

		# expense account gl entries
		if cint(frappe.defaults.get_global_default("auto_accounting_for_stock")) \
				and cint(self.update_stock):
				
			# because these come in proper polarities 
			# so to switch back, switch polarity now
			for gl in super(SalesReturn, self).get_gl_entries():
				if gl.debit:
					gl.debit *= -1
					gl.debit_in_account_currency *= -1
				elif gl.credit:
					gl.credit *= -1
					gl.credit_in_account_currency *= -1
					
				gl_entries.append(gl)
			# gl_entries += super(SalesReturn, self).get_gl_entries()
			
			
	def make_pos_gl_entries(self, gl_entries):
		if cint(self.is_pos):
			gl_entries.append(
				self.get_gl_dict({
					"account": self.debit_to,
					"party_type": "Customer",
					"party": self.customer,
					"against": self.cash_bank_account,
					"credit": self.base_grand_total,
					"credit_in_account_currency": self.base_grand_total \
						if self.party_account_currency==self.company_currency \
						else self.grand_total,
					"against_voucher": self.name,
					"against_voucher_type": self.doctype,
				}, self.party_account_currency)
			)

			payment_mode_account_currency = get_account_currency(self.cash_bank_account)
			gl_entries.append(
				self.get_gl_dict({
					"account": self.cash_bank_account,
					"against": self.customer,
					"debit": self.base_grand_total,
					"debit_in_account_currency": self.base_grand_total \
						if payment_mode_account_currency==self.company_currency \
						else self.grand_total
				}, payment_mode_account_currency)
			)
					
					
	def make_gle_for_change_amount(self, gl_entries):
		if cint(self.is_pos) and self.change_amount:
			if self.account_for_change_amount:
				gl_entries.append(
					self.get_gl_dict({
						"account": self.debit_to,
						"party_type": "Customer",
						"party": self.customer,
						"against": self.account_for_change_amount,
						"debit": flt(self.base_change_amount),
						"debit_in_account_currency": flt(self.base_change_amount) \
							if self.party_account_currency==self.company_currency else flt(self.change_amount),
						"against_voucher": self.name,
						"against_voucher_type": self.doctype
					}, self.party_account_currency)
				)

				gl_entries.append(
					self.get_gl_dict({
						"account": self.account_for_change_amount,
						"against": self.customer,
						"credit": self.base_change_amount
					})
				)
			else:
				frappe.throw(_("Select change amount account"), title="Mandatory Field")

				
	def make_write_off_gl_entry(self, gl_entries):
		# write off entries, applicable if only pos
		if self.write_off_account and self.write_off_amount:
			write_off_account_currency = get_account_currency(self.write_off_account)
			default_cost_center = frappe.db.get_value('Company', self.company, 'cost_center')

			gl_entries.append(
				self.get_gl_dict({
					"account": self.debit_to,
					"party_type": "Customer",
					"party": self.customer,
					"against": self.write_off_account,
					"credit": self.base_write_off_amount,
					"credit_in_account_currency": self.base_write_off_amount \
						if self.party_account_currency==self.company_currency else self.write_off_amount,
					"against_voucher": self.name,
					"against_voucher_type": self.doctype
				}, self.party_account_currency)
			)
			gl_entries.append(
				self.get_gl_dict({
					"account": self.write_off_account,
					"against": self.customer,
					"debit": self.base_write_off_amount,
					"debit_in_account_currency": self.base_write_off_amount \
						if write_off_account_currency==self.company_currency else self.write_off_amount,
					"cost_center": self.write_off_cost_center or default_cost_center
				}, write_off_account_currency)
			)