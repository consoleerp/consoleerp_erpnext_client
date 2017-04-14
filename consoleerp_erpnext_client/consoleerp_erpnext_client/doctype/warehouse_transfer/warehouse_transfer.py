# -*- coding: utf-8 -*-
# Copyright (c) 2015, Console ERP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, nowdate, nowtime, cint, cstr, formatdate, format_time, comma_and
from erpnext.stock.utils import get_incoming_rate
from erpnext.stock.stock_ledger import get_previous_sle, NegativeStockError
from erpnext.stock.get_item_details import get_conversion_factor, get_default_cost_center
from frappe.model.mapper import get_mapped_doc
from frappe.model.document import Document
from erpnext.controllers.stock_controller import StockController
import json

class WarehouseTransfer(StockController):
	
	def validate(self):
		
		# in transaction base
		# validates pos
		# CHECK THIS FOR V8		
		self.validate_posting_time()
		
		# defines self.transfer_buffer_warehouse
		self.get_transfer_buffer_warehouse()
		self.set_transfer_qty()
		self.set_actual_qty()
		self.calculate_rate_and_amount()
				
	def on_submit(self):
		self.update_stock_ledger()
		
		from erpnext.stock.doctype.serial_no.serial_no import update_serial_nos_after_submit
		# there is no child_doc.warehouse present, only child_doc.s_warehouse
		# we have to add the attribute
		for d in self.get("items"):
			d.warehouse = d.s_warehouse;
		update_serial_nos_after_submit(self, "items")			
		self.make_gl_entries()
		self.reference_update()
		
	def on_cancel(self):
		
		self.check_related_docs()
		# defines self.transfer_buffer_warehouse
		self.get_transfer_buffer_warehouse()
		self.update_stock_ledger()
		self.make_gl_entries_on_cancel()
		self.reference_update();
		
		
	def reference_update(self):
		"""
		Warehouse Transfer Detail has the field reference_warehouse_transfer
		TODO -- replaces `status` field updation by StatusUpdater, its one of the base class of StockController
		"""
		if self.purpose == "Transfer Receive":
			# for now, we will get the reference w transfer from row1 and update it over simply
			ref_wt = self.get('items')[0].reference_warehouse_transfer
			if ref_wt:
				current_status = frappe.db.get_value("Warehouse Transfer", ref_wt, "status")
				if current_status != "Issued":
					frappe.throw(_("Can receive items from a issued Warehouse Transfer transaction only"))
					
				# this is called either on cancel or on submit
				new_status = self.docstatus == 1 and "Received" or "Issued"
				frappe.db.set_value("Warehouse Transfer", ref_wt, "status", new_status)
				
				# for the current doc
				status = self.docstatus == 1 and "Received" or "Open"
				self.db_set("status", status)
				#frappe.db.set_value("Warehouse Transfer", self.name, "status", "Received")
		else:
			# Transfer Issue
			# on cancel -- open, submitted- 
			# setting self.status doesnt work, saving of doc is done before this is called, we have to use self.db_set (inherited from BaseDocument)
			# this is how erpnext status updater updates status even after submission
			status = self.docstatus == 1 and "Issued" or "Open"
			# RESEARCH
			self.db_set("status", status)
			#frappe.db.set_value("Warehouse Transfer", self.name, "status", status)			
				
	def check_related_docs(self):
		"""
		Checks if any other warehouse transfer related to this exists, if exists- prevents cancelling
		"""
		
		# erpnext allows cancellation when the other related doc is not submitted. we are not doing it here
		wts = frappe.db.sql_list("""select t1.name from `tabWarehouse Transfer` t1, `tabWarehouse Transfer Detail` t2
				where t2.parent = t1.name and t2.reference_warehouse_transfer = %s""", self.name)
				
		# RESEARCH comma_and
		if wts:
			frappe.throw(_("Warehouse Transfer {0} must be cancelled before cancelling this Warehouse Transfer").format(comma_and(wts)))
	
	def update_stock_ledger(self):
		sl_entries = []				
		
		# make sl entries for source warehouse first, then do for target warehouse
		# RESEARCH why do all items together ? why not src, target, src, target, like for each item ?
		for d in self.get('items'):
			sl_entries.append(self.get_sl_entries(d, {
				"warehouse": cstr(self.purpose == "Transfer Issue" and d.s_warehouse or self.transfer_buffer_warehouse),
				"actual_qty": -flt(d.transfer_qty),
				"incoming_rate": 0
			}))
			
		for d in self.get('items'):
			sl_entries.append(self.get_sl_entries(d, {
				"warehouse": cstr(self.purpose == "Transfer Receive" and d.t_warehouse or self.transfer_buffer_warehouse),
				"actual_qty": flt(d.transfer_qty),
				"incoming_rate": flt(d.valuation_rate)
			}))
			
		# on cancel, reverse the entries
		if self.docstatus == 2:
			sl_entries.reverse()
		
		self.make_sl_entries(sl_entries, self.amended_from and 'Yes' or 'No')
		
	def set_transfer_qty(self):
		for d in self.get("items"):
			if not flt(d.qty):
				frappe.throw(_("Row {0}: Qty is mandatory").format(d.idx))
			if not flt(d.conversion_factor):
				frappe.throw(_("Row {0}: UOM Conversion Factor is mandatory").format(d.idx))
			d.transfer_qty = flt(flt(d.qty) * flt(d.conversion_factor), d.precision("transfer_qty"))
	
	def calculate_rate_and_amount(self, force=False, update_finished_item_rate=True):
		self.set_basic_rate(force, update_finished_item_rate)
		self.distribute_additional_costs()
		self.update_valuation_rate()
		
	def set_basic_rate(self, force=False, update_finished_item_rate=True):
		"""get stock and incoming rate on posting date [FORCED]"""
		for d in self.get("items"):
			# RESEARCH -- dict like objects that exposes keys as attributes
			args = frappe._dict({
				"item_code"		: d.item_code,
				"warehouse"		: d.s_warehouse,
				"posting_date"	: self.posting_date,
				"posting_time"	: self.posting_time,
				"qty"			: -1 * flt(d.transfer_qty),
				"serial_no"		: d.serial_no
			})
			# RESEARCH -- precision: self.precision, doc.precision (two lines below)
			basic_rate = flt(get_incoming_rate(args), self.precision("basic_rate", d))
			if basic_rate > 0:
				d.basic_rate = basic_rate
			
			d.basic_amount = flt(flt(d.transfer_qty) * flt(d.basic_rate), d.precision("basic_amount"))
	
	def get_transfer_buffer_warehouse(self):
		self.transfer_buffer_warehouse = frappe.db.get_value("ConsoleERP Settings", None, "transfer_buffer_warehouse")
		if not self.transfer_buffer_warehouse:
			frappe.throw(_("Please define the buffer warehouse in ConsoleERP Settings"))	
	
	def distribute_additional_costs(self):
		self.total_additional_costs = sum([flt(t.amount) for t in self.get("additional_costs")])
		total_basic_amount = sum([flt(t.basic_amount) for t in self.get("items")])
			
		for d in self.get("items"):
			d.additional_costs = (flt(d.basic_amount) / total_basic_amount) * self.total_additional_costs
			
	def update_valuation_rate(self):
		for d in self.get("items"):
			d.amount = flt(flt(d.basic_rate) + flt(d.basic_amount), d.precision("amount"))
			d.valuation_rate = flt(flt(d.basic_rate) + flt(d.additional_cost) / flt(d.transfer_qty), d.precision("valuation_rate"))
			
	def set_actual_qty(self):
		allow_negative_stock = cint(frappe.db.get_value("Stock Settings", fieldname="allow_negative_stock"))
		
		for d in self.get("items"):
				# RESEARCH
				s_warehouse_previous_sle = get_previous_sle({
					"item_code" 	: d.item_code,
					"warehouse" 	: d.s_warehouse,
					"posting_date"	: self.posting_date,
					"posting_time"	: self.posting_time
				})							
				
				"""				
				On submitting Transfer Receive, we have to check from Transfer Buffer Warehouse. not source warehouse
				but still we have to give the actual qty at source
				"""
				buffer_warehouse_previous_sle = get_previous_sle({
					"item_code" 	: d.item_code,
					"warehouse" 	: self.transfer_buffer_warehouse,
					"posting_date"	: self.posting_date,
					"posting_time"	: self.posting_time
				})
				
				# get actual stock at source warehouse
				d.actual_qty = s_warehouse_previous_sle.get("qty_after_transaction") or 0
				
				test_actual_qty = self.purpose == "Transfer Issue" and d.actual_qty or buffer_warehouse_previous_sle.get("qty_after_transaction")
				
				# validate qty during submit
				if d.docstatus == 1 and not allow_negative_stock and test_actual_qty < d.transfer_qty:
					frappe.throw(_("Row {0}: Qty not available for {4} in warehouse {1} at posting time of the entry ({2} {3})").format(d.idx,
						frappe.bold(d.s_warehouse), formatdate(self.posting_date),
						format_time(self.posting_time), frappe.bold(d.item_code))
						+ '<br><br>' + _("Available qty is {0}, you need {1}").format(frappe.bold(d.actual_qty),
							frappe.bold(d.transfer_qty)),
						NegativeStockError, title=_('Insufficient Stock'))
	
	def get_item_details(self, args=None, for_update=False):
		# referenced from stock_entry.py
		# is called when item_code is changed
		
		item = frappe.db.sql("""select stock_uom, description, image, item_name, item_group,
				expense_account, buying_cost_center
				from `tabItem` 
				where name = %s
						and disabled = 0
						and (end_of_life is null or end_of_life='0000-00-00' or end_of_life > %s)""",
						(args.get('item_code'), nowdate()), as_dict=1)
		
		if not item:
			frappe.throw(_("Item {0} is not active or end of life has been reached.").format(args.get('item_code')))
			
		item = item[0]
		
		# expense_account and cost_centers are not applicable in warehouse transfer.
		
		ret = {
			'uom'				: item.stock_uom,
			'stock_uom'			: item.stock_uom,
			'description'		: item.description,
			'image'				: item.image,
			'item_name'			: item.item_name,
			'expense_account'	: args.get("expense_account"),
			'cost_center'		: get_default_cost_center(args, item),
			'qty'				: 0,
			'transfer_qty'		: 0,
			'conversion_factor'	: 1,
			'actual_qty'		: 0,
			'basic_rate'		: 0,
			'batch_no'			: '',
			'serial_no'			: ''
		}
		
		# setting default expense account or cost center for the company unless specified
		# also validates if the account or cost center is coming from the current company
		for d in [["Account", "expense_account", "default_expense_account"],
				["Cost Center", "cost_center", "cost_center"]]:
						company = frappe.db.get_value(d[0], ret.get(d[1]), "company")
						if not ret[d[1]] or (company and self.company != company):
							ret[d[1]] = frappe.db.get_value("Company", self.company, d[2]) if d[2] else None
		
		# V8
		# whitelisted methods
		# from erpnext.stock.doctype.stock_entry.stock_entry import get_uom_details, get_warehouse_details
		
		# update uom
		if args.get('uom') and for_update:
			ret.update(get_uom_details(args.get('item_code'), args.get('uom'), args.get('qty')))
			
		args["posting_time"] = self.posting_time
		args["posting_date"] = self.posting_date
		
		stock_and_rate = args.get('warehouse') and get_warehouse_details(args) or {}
		ret.update(stock_and_rate)
		
		return ret				

	def reset_posting_time(self):
		self.posting_date = nowdate()
		self.posting_time = nowtime()
		frappe.msgprint(nowdate() + " -- " + nowtime())
		
	def get_gl_entries(self, warehouse_account):
		expenses_included_in_valuation = self.get_company_default("expenses_included_in_valuation")
		
		gl_entries = super(WarehouseTransfer, self).get_gl_entries(warehouse_account)
		
		# if additional_cost is present, make gl entry between expense_account and expense_included_in_valuation account
		for d in self.get('items'):
			additional_cost = flt(d.additional_cost, d.precision("additional_cost"))
			if additional_cost:
				gl_entries.append(self.get_gl_dict({
					"account": expenses_included_in_valuation,
					"against": d.expense_account,
					"cost_center": d.cost_center,
					"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
					"credit": additional_cost
				}))

				gl_entries.append(self.get_gl_dict({
					"account": d.expense_account,
					"against": expenses_included_in_valuation,
					"cost_center": d.cost_center,
					"remarks": self.get("remarks") or _("Accounting Entry for Stock"),
					"credit": -1 * additional_cost # put it as negative credit instead of debit purposefully
				}))
			
		return gl_entries
		
@frappe.whitelist()
def receive_items(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.purpose = "Transfer Receive"
		target.run_method("reset_posting_time") 		

	doclist = get_mapped_doc("Warehouse Transfer", source_name, {
				"Warehouse Transfer": {
					"doctype": "Warehouse Transfer",
					"validation": {
						"docstatus": ["=", 1]
					}
				},
				"Warehouse Transfer Detail": {
					"doctype":"Warehouse Transfer Detail",
					"field_map": {
						# RESEARCH-- name, parent, condition- delivered items are filtered here -- Refer Sales Order > Delivery Note 
						"parent": "reference_warehouse_transfer"
					}
				},
				"Landed Cost Taxes and Charges": {
					"doctype": "Landed Cost Taxes and Charges"
				}
			}, target_doc, set_missing_values, ignore_permissions=False)
	
	return doclist
# DELETE THE FOLLOWING METHODS AFTER PROPER MIGRATE TO V8 and REFER THESE METHODS FROM stock_entry.py	
# V8	

@frappe.whitelist()
def get_uom_details(item_code, uom, qty):
	"""Returns dict `{"conversion_factor": [value], "transfer_qty": qty * [value]}`
	:param args: dict with `item_code`, `uom` and `qty`"""
	conversion_factor = get_conversion_factor(item_code, uom).get("conversion_factor")

	if not conversion_factor:
		frappe.msgprint(_("UOM coversion factor required for UOM: {0} in Item: {1}")
			.format(uom, item_code))
		ret = {'uom' : ''}
	else:
		ret = {
			'conversion_factor'		: flt(conversion_factor),
			'transfer_qty'			: flt(qty) * flt(conversion_factor)
		}
	return ret

@frappe.whitelist()
def get_warehouse_details(args):
	if isinstance(args, basestring):
		args = json.loads(args)

	args = frappe._dict(args)

	ret = {}
	if args.warehouse and args.item_code:
		args.update({
			"posting_date": args.posting_date,
			"posting_time": args.posting_time,
		})
		ret = {
			"actual_qty" : get_previous_sle(args).get("qty_after_transaction") or 0,
			"basic_rate" : get_incoming_rate(args)
		}

	return ret		