# Copyright (c) 2013, Console ERP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, getdate, cstr

def execute(filters=None):		
	validate_filters(filters)
	
	columns, data = get_columns(filters), get_data(filters)
	print("\n\n\n=================================")
	print(columns)
	print("===================================\n\n")
	print(data)
	print("===================================\n\n")
	return columns, data
		
def validate_filters(filters):
	if not filters.get('company'):
		frappe.throw(_('{0} is mandatory').format(_('Company')))

	party_type, party = filters.get("party_type"), filters.get("party")

	if party:
		if not party_type:
			frappe.throw(_("To filter based on Party, select Party Type first"))
		elif not frappe.db.exists(party_type, party):
			frappe.throw(_("Invalid {0}: {1}").format(party_type, party))

	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date must be before To Date"))
		
def get_columns(filters):
	"""
	if summary:
		Party Type, Party, Opening Balance, Debit, Credit, Balance
	else:
		Posting Date, Party Type, Party, Debit, Credit, Balance, Voucher Type, Voucher No, Remarks
	"""
	if filters.get("summary_report"):
		return [
			_("Party Type") + "::120", _("Party") + ":Dynamic Link/"+_("Party Type")+":160",
			_("Opening Balance") + ":Float:100",
			_("Debit") + ":Float:100", _("Credit") + ":Float:100", _("Balance") + ":Float:100"
		]
	else:
		return [
			_("Posting Date") + ":Date:90",
			_("Voucher Type") + "::120", _("Voucher No") + ":Dynamic Link/"+_("Voucher Type")+":130",
			_("Party") + ":Dynamic Link/"+_("Party Type")+":160",			
			_("Debit") + ":Float:100", _("Credit") + ":Float:100", _("Balance") + ":Float:100",						
			_("Party Type") + "::120", _("Remarks") + "::400"
		]

def get_data(filters):
	gl_entries = get_gl_entries(filters)	
	data = get_data_with_opening_closing(filters, gl_entries)
	print("data")
	print(data)
	result = get_result_as_list(data, filters)
	return result
	
def get_gl_entries(filters):
	"""
	Get the gl entries
	posting_date >= from_date condition is nto considered here, since we want balance in all types
	"""
	return frappe.db.sql("""
	select
		posting_date, account, party_type, party,
		sum(debit) as debit, sum(credit) as credit,
		voucher_type, voucher_no, remarks, is_opening
	from `tabGL Entry`
	where company=%(company)s {conditions}
	group by voucher_type, voucher_no, party_type, party
	order by posting_date, party_type, party"""\
	.format(conditions=get_conditions(filters)), filters, as_dict=1, debug=1)
	
def get_conditions(filters):
	conditions = []
	if filters.get("party_type"):		
		conditions.append("party_type=%(party_type)s")
	else:
		conditions.append("party_type in ('Customer', 'Supplier')")
		
	if filters.get("party"):
		conditions.append("party=%(party)s")
		
	from frappe.desk.reportview import build_match_conditions
	match_conditions = build_match_conditions("GL Entry")
	if match_conditions: conditions.append(match_conditions)
	
	return "and {}".format(" and ".join(conditions)) if conditions else ""
	
def get_data_with_opening_closing(filters, gl_entries):
	data = []
	gle_map = initialize_gle_map(gl_entries)
	gle_map = get_partywise_gle(filters, gl_entries, gle_map)
	
	party_types = ["Customer", "Supplier"]
	
	if filters.get("summary_report"):		
		for party_type in party_types:
			for party, party_dict in gle_map[party_type].items():
				if party_dict.entries:
					# summary report
					data.append({
						'party_type': party_type,
						'party': party, 
						'opening': party_dict.opening,
						'debit': party_dict.total_debit, 
						'credit': party_dict.total_credit,
						'balance': party_dict.opening + party_dict.total_debit - party_dict.total_credit
					})
	else:
		for party_type in party_types:			
			for party, party_dict in gle_map[party_type].items():
				if party_dict.entries:
					# detail report
					# opening is negative if opening balance is credit
					total_debit = party_dict.total_debit + party_dict.opening if party_dict.opening > 0 else party_dict.total_debit
					total_credit = party_dict.total_credit +(-1 * party_dict.opening) if party_dict.opening < 0 else party_dict.total_credit
					#opening row
					data.append(get_balance_row(_("Opening"), party_dict.opening))
					data += party_dict.entries
					data += [{
							'party': "'" +_("Totals") + "'", 
							"debit": total_debit, 
							"credit": total_credit,
							"balance": total_debit - total_credit
							},	{}]
					
	return data
	
def initialize_gle_map(gl_entries):
	gle_map = {"Customer": frappe._dict(), "Supplier": frappe._dict()}		
	for gle in gl_entries:
		gle_map[gle.party_type].setdefault(gle.party, frappe._dict({
					"opening": 0,
					"entries": [],
					"total_debit": 0,
					"total_credit": 0,
					"closing": 0				
		}))
	return gle_map
	
def get_partywise_gle(filters, gl_entries, gle_map):

	from_date, to_date = getdate(filters.from_date), getdate(filters.to_date)
	for gle in gl_entries:
		balance = flt(gle.debit, 3) - flt(gle.credit, 3)
		# add balance to the gle_row
		gle["balance"] = balance
		
		if gle.posting_date < from_date or cstr(gle.is_opening) == "Yes":
			gle_map[gle.party_type][gle.party].opening += balance
		elif gle.posting_date <= to_date:
			party_dict = gle_map[gle.party_type][gle.party]
			
			balance = party_dict.entries[-1].balance if party_dict.entries else 0
			balance += gle.debit
			balance -= gle.credit
			gle["balance"] = balance
			
			party_dict.entries.append(gle)
			party_dict.total_debit += flt(gle.debit, 3)
			party_dict.total_credit += flt(gle.credit, 3)
			
	return gle_map
	
def get_balance_row(label, balance):
	return {
		"party": "'" + label + "'",
		"debit": balance if balance > 0 else 0,
		"credit": -1*balance if balance < 0 else 0,
		"balance": balance
	}

def get_result_as_list(data, filters):
	result = []
	if filters.get("summary_report"):
		for d in data:
			result.append([
				d.get("party_type"), d.get("party"),
				d.get("opening"),
				d.get("debit"), d.get("credit"), d.get("balance")
			])			
	else:
		for d in data:
			result.append([
				d.get("posting_date"),
				d.get("voucher_type"), d.get("voucher_no"),	
				d.get("party"),
				d.get("debit"), d.get("credit"), d.get("balance"),						
				d.get("party_type"), d.get("remarks")
			])
	return result