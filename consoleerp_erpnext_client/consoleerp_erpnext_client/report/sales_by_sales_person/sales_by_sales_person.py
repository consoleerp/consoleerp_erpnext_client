# Copyright (c) 2013, Console ERP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
	columns, data = [], []
	return columns, data

def validate_filters(filters):
	if not filters.get('company'):
		frappe.throw(_('{0} is mandatory').format(_('Company')))

def get_columns(filters):
	"""
	If summary_report:
		Sales Person, Gross, Discount, Net, Profit, Profit %
	else:
		Date, Sales Person, Invoice No, Customer, Gross, Discount, Net Territory, Doctype 
	"""
	return [
	]