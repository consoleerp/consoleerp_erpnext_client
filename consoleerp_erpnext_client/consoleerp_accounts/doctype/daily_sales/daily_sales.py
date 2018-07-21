# -*- coding: utf-8 -*-
# Copyright (c) 2018, Console ERP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from erpnext.controllers.accounts_controller import AccountsController
from erpnext.accounts.party import get_party_account
from frappe.utils import flt
from erpnext.accounts.utils import get_account_currency
from erpnext.setup.utils import get_exchange_rate
from erpnext import get_company_currency, get_default_cost_center

class DailySales(AccountsController):

	def on_submit(self):
		self.make_gl_entries()
	
	def on_cancel(self):
		self.make_gl_entries()
	
	def validate(self):
		self.set_conversion_rate()
		self.validate_debit_acc()
		self.calculate_totals()
		self.set_customer_receivable_accounts()
		
	def make_gl_entries(self):
		gl_entries = []
		
		# cash
		if self.debit_to == "Employee":
			cash_debit_account = frappe.get_value("Company", self.company, "default_employee_advance_account")
			if not cash_debit_account:
				frappe.throw("Please define default employee advance account for the Company")
		else:
			cash_debit_account = self.debit_account
		
		income_account = self.get_income_account()
		cost_center = get_default_cost_center(self.company)
		
		# CASH ENTRY AGAINST INCOME ACCOUNT
		gl_entries.append(
			self.get_gl_dict({
				"account": income_account,
				"against": self.debit_employee if self.debit_to == "Employee" else self.debit_account,
				"credit": self.base_total_cash_sales,
				"cost_center": cost_center
			})
		)
		
		gl_entries.append(
			self.get_gl_dict({
				"account": cash_debit_account,
				"against": income_account,
				"debit": self.base_total_cash_sales,
				"party_type": "Employee" if self.debit_to == "Employee" else None,
				"party": self.debit_employee if self.debit_to == "Employee" else None
			})
		)
		
		# CREDIT ENTRY AGAINST INCOME ACCOUNT
		for cc in self.credit_sales:
			gl_entries.append(
				self.get_gl_dict({
					"account": income_account,
					"against": cc.customer,
					"credit": cc.base_amount,
					"cost_center": cost_center
				})
			)
			
			gl_entries.append(
				self.get_gl_dict({
					"account": cc.receivable_account,
					"against": income_account,
					"debit": cc.base_amount,
					"party_type": "Customer",
					"party": cc.customer
				})
			)
		
		from erpnext.accounts.general_ledger import make_gl_entries
		make_gl_entries(gl_entries, cancel=(self.docstatus == 2),
		update_outstanding='Yes', merge_entries=False)
	
	def calculate_totals(self):
		self.total_credit_sales = 0
		for credit in self.credit_sales:
			self.total_credit_sales += credit.amount or 0
			credit.base_amount = credit.amount * self.conversion_rate
			
		self.total = flt(self.total_cash_sales + self.total_credit_sales, self.precision("total"))
		
		self.base_total_cash_sales = self.total_cash_sales * self.conversion_rate
		self.base_total_credit_sales = self.total_credit_sales * self.conversion_rate
		self.base_total = self.total * self.conversion_rate
		
	
	def get_income_account(self):
		# TODO: Implement POS Profile here
		accounts_details = frappe.get_all("Company",
			fields=["default_receivable_account", "default_income_account", "cost_center"],
			filters={"name": self.company})[0]
		return accounts_details.default_income_account
	
	def validate_debit_acc(self):
		if self.debit_to == "Employee":
			if not self.debit_employee:
				frappe.throw("Please select an Employee to debit to")
			self.debit_account = None
		elif self.debit_to == "Account":
			if not self.debit_account:
				frappe.throw("Please select a debit account")
			self.debit_employee = None
		else:
			frappe.throw("Debit To is mandatory")
			
	def set_conversion_rate(self):
		self.conversion_rate = get_exchange_rate(self.currency, get_company_currency(self.company), self.posting_date)
	
	def set_customer_receivable_accounts(self):
		for cc in self.credit_sales:
			cc.receivable_account = get_party_account("Customer", cc.customer, self.company)