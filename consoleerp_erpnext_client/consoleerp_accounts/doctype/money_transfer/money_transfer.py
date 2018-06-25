# -*- coding: utf-8 -*-
# Copyright (c) 2018, Console ERP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from erpnext.controllers.accounts_controller import AccountsController
from erpnext.accounts.utils import get_account_currency
from erpnext.setup.utils import get_exchange_rate
from erpnext import get_company_currency

class MoneyTransfer(AccountsController):

	def on_submit(self):
		self.make_gl_entries()
	
	def on_cancel(self):
		self.make_gl_entries()
	
	
	def make_gl_entries(self):
		gl_entries = []
		
		from_account = self.get_from_account()
		from_account_currency = get_account_currency(from_account)
		gl_entries.append(
			self.get_gl_dict({
				"account": from_account,
				"against": self.to, # account or employee
				"credit": self.base_amount,
				"credit_in_account_currency": self.amount,
				"party_type": "Employee" if self.from_type == "Employee" else None,
				"party": self.get("from") if self.from_type == "Employee" else None
			}, from_account_currency)
		)
		
		to_account = self.get_to_account()
		to_account_currency = get_account_currency(to_account)
		company_currency = get_company_currency(self.company)
		to_exchange_rate = get_exchange_rate(company_currency, to_account_currency, self.posting_date)
		gl_entries.append(
			self.get_gl_dict({
				"account": to_account,
				"against": self.get("from"), # account or employee
				"debit": self.base_amount,
				"debit_in_account_currency": self.base_amount * to_exchange_rate,
				"party_type": "Employee" if self.to_type == "Employee" else None,
				"party": self.get("to") if self.to_type == "Employee" else None
			}, to_account_currency)
		)
		
		from erpnext.accounts.general_ledger import make_gl_entries
		make_gl_entries(gl_entries, cancel=(self.docstatus == 2),
		update_outstanding='Yes', merge_entries=False)
	
	def validate(self):
		self.validate_types()
		self.validate_accounts()
		self.validate_employee()
		
		if self.get("from") == self.to:
			frappe.throw("Cant transfer between same accounts")
			
		if not self.amount > 0:
			frappe.throw("Amount should be greater than 0")
		
		self.set_base_amount()
		
	
	def validate_types(self):
		types = ["Employee", "Account"]
		if self.from_type not in types or self.to_type not in types:
			frappe.throw("Invalid Transfer Type")

	def validate_accounts(self):
		def validate_account(account):
			acc = frappe.get_value("Account", account, ["name", "account_type", "root_type", "is_group", "company"], as_dict=1)
			
			if acc.company != self.company:
				frappe.throw("Account is not of this company")
			
			if acc.is_group:
				frappe.throw("Account should not be a group")
			
			if acc.account_type not in ["Cash", "Bank"]:
				frappe.throw("Account should be cash or bank account. The Account {} is of Type {}".format(account, acc.account_type))
			
			if acc.root_type != "Asset":
				frappe.throw("Account should be an Asset Account")
		
		if self.from_type == "Account":
			validate_account(self.get("from"))
		if self.to_type == "Account":
			validate_account(self.to)
	
	def validate_employee(self):
		employee_receivable_account = frappe.get_value("Company", self.company, "default_employee_advance_account")
		
		if self.from_type == "Employee":
			if not self.from_receivable_payable:
				if employee_receivable_account:
					self.from_receivable_payable = employee_receivable_account
				else:
					frappe.throw("From Receivable Undefined for Employee Type")
		
		if self.to_type == "Employee":
			if not self.to_receivable_payable:
				if employee_receivable_account:
					self.to_receivable_payable = employee_receivable_account
				else:
					frappe.throw("From Receivable Undefined for Employee Type")
	
	def set_base_amount(self):
		from_account_currency = get_account_currency(self.get_from_account())
		exchange_rate = get_exchange_rate(from_account_currency, get_company_currency(self.company), self.posting_date)
		
		self.base_amount = self.amount * exchange_rate
	
	def get_from_account(self):
		return self.get("from") if self.from_type == "Account" else self.from_receivable_payable
		
	def get_to_account(self):
		return self.to if self.to_type == "Account" else self.to_receivable_payable