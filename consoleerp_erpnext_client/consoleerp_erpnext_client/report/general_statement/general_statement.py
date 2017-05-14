# Copyright (c) 2013, Console ERP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

# import General Ledger
from erpnext.accounts.report.general_ledger.general_ledger import validate_filters, validate_party, set_account_currency, get_columns, get_result

def execute(filters=None):
	
	account_details = {}
	for acc in frappe.db.sql("""select name, is_group from tabAccount""", as_dict=1):
		account_details.setdefault(acc.name, acc)

	validate_filters(filters, account_details)

	validate_party(filters)

	filters = set_account_currency(filters)

	columns = get_columns(filters)
	#inserting balance column
	columns.insert(4, _("Balance") + ":Float:100")
	# if show in show_in_account_currency
	if filters.get("show_in_account_currency"):
		columns.insert(7, _("Balance") + " (" + filters.account_currency + ")" + ":Float:100")
	
	res = get_result(filters, account_details)
	
	# insert balance values
	balance = 0
	row_ignore_calc = ["'" + _("Closing (Opening + Totals)") + "'", "'" +  _("Totals") + "'"]
	for row in res:
		if row[1] not in row_ignore_calc:
			balance = balance + row[2] if row[2] != None else balance
			balance = balance - row[3] if row[3] != None else balance
		
		# insert only if there is value in credit or debit
		# donot insert when not 
		insert = row[2] or row[3]
		if insert != None:
			row.insert(4, balance)
	
	return columns, res
