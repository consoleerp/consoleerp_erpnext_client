# Copyright (c) 2013, Console ERP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import flt, getdate, cstr

def execute(filters=None):		
	validate_filters(filters)
	
	columns, data = get_columns(filters), get_data(filters)
	return columns, data
		
def validate_filters(filters):
	if not filters.get('company'):
		frappe.throw(_('{0} is mandatory').format(_('Company')))	

	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date must be before To Date"))
		
def get_columns(filters):
	"""
	if summary:
		Consolidation Code, Opening Balance, Debit, Credit, Balance
	else:
		Posting Date, Party Type, Party, Debit, Credit, Balance, Voucher Type, Voucher No, Remarks
	"""
	if filters.get("summary_report"):
		return [
			_("Consolidation Code") + ":Link/"+_("Consolidation")+":160",	
			_("Opening Balance") + ":Float:100",
			_("Debit") + ":Float:100", _("Credit") + ":Float:100", _("Balance") + ":Float:100"
		]
	else:
		return [
			_("Posting Date") + ":Date:90",
			_("Consolidation Code") + ":Link/"+_("Consolidation")+":160",	
			_("Voucher Type") + "::120", _("Voucher No") + ":Dynamic Link/"+_("Voucher Type")+":130",
			_("Party") + ":Dynamic Link/"+_("Party Type")+":160",			
			_("Debit") + ":Float:100", _("Credit") + ":Float:100", _("Balance") + ":Float:100",						
			_("Party Type") + "::120", _("Remarks") + "::400"
		]

def get_data(filters):
	gl_entries = get_gl_entries(filters)	
	data = get_data_with_opening_closing(filters, gl_entries)
	result = get_result_as_list(data, filters)
	return result
	
def get_gl_entries(filters):
	"""
	Get the gl entries
	posting_date >= from_date condition is nto considered here, since we want balance in all types
	"""
	return frappe.db.sql("""
	select * from
		(select
			c.parent as consolidation_code,
			posting_date, account, gl.party_type, gl.party,
			sum(debit) as debit, sum(credit) as credit,
			voucher_type, voucher_no, remarks, is_opening
		from `tabGL Entry` gl left join `tabConsolidation Item` c on c.party = gl.party
		where company=%(company)s
		group by voucher_type, voucher_no) tb
		where {conditions}
		order by posting_date, party_type, party"""\
	.format(conditions=get_conditions(filters)), filters, as_dict=1, debug=1)
	
def get_conditions(filters):
	conditions = []
	
	# all Customer and Supplier GLs
	conditions.append("party_type in ('Customer', 'Supplier')")	
		
	if filters.get("consolidation_code"):
		conditions.append("party in (select party from `tabConsolidation Item` where parent = %(consolidation_code)s)")
	else:
		conditions.append("party in (select party from `tabConsolidation Item`)")
		
	from frappe.desk.reportview import build_match_conditions
	match_conditions = build_match_conditions("GL Entry")
	if match_conditions: conditions.append(match_conditions)
	
	return "{}".format(" and ".join(conditions)) if conditions else ""
	
def get_data_with_opening_closing(filters, gl_entries):
	data = []
	gle_map = initialize_gle_map(gl_entries)
	gle_map = get_consolidation_wise_gle(filters, gl_entries, gle_map)
	
	if filters.get("summary_report"):				
		for consolidation_code, consolidation_dict in gle_map.items():
			if consolidation_dict.entries:
				# summary report
				data.append({
					'consolidation_code': consolidation_code,
					'opening': consolidation_dict.opening,
					'debit': consolidation_dict.total_debit, 
					'credit': consolidation_dict.total_credit,
					'balance': consolidation_dict.opening + consolidation_dict.total_debit - consolidation_dict.total_credit
				})
	else:			
		for consolidation_code, consolidation_dict in gle_map.items():
			if consolidation_dict.entries:
				# detail report
				# opening is negative if opening balance is credit
				total_debit = consolidation_dict.total_debit + consolidation_dict.opening if consolidation_dict.opening > 0 else consolidation_dict.total_debit
				total_credit = consolidation_dict.total_credit +(-1 * consolidation_dict.opening) if consolidation_dict.opening < 0 else consolidation_dict.total_credit
				#opening row
				data.append(get_balance_row(_("Opening"), consolidation_dict.opening))
				data += consolidation_dict.entries
				data += [{
						'party': "'" +_("Totals") + "'", 
						"debit": total_debit, 
						"credit": total_credit,
						"balance": total_debit - total_credit
						},	{}]
					
	return data
	
def initialize_gle_map(gl_entries):
	gle_map = frappe._dict()		
	for gle in gl_entries:
		gle_map.setdefault(gle.consolidation_code, frappe._dict({
					"opening": 0,
					"entries": [],
					"total_debit": 0,
					"total_credit": 0,
					"closing": 0				
		}))
	return gle_map
	
def get_consolidation_wise_gle(filters, gl_entries, gle_map):

	from_date, to_date = getdate(filters.from_date), getdate(filters.to_date)
	for gle in gl_entries:
		balance = flt(gle.debit, 3) - flt(gle.credit, 3)
		# add balance to the gle_row
		gle["balance"] = balance
		
		if gle.posting_date < from_date or cstr(gle.is_opening) == "Yes":
			gle_map[gle.consolidation_code].opening += balance
		elif gle.posting_date <= to_date:
			consolidation_dict = gle_map[gle.consolidation_code]
			
			balance = consolidation_dict.entries[-1].balance if consolidation_dict.entries else 0
			balance += gle.debit
			balance -= gle.credit
			gle["balance"] = balance
			
			if gle.debit >= gle.credit:
				gle.debit -= gle.credit
				gle.credit = 0
			else:
				gle.credit -= gle.debit
				gle.debit = 0;
			
			consolidation_dict.entries.append(gle)
			consolidation_dict.total_debit += flt(gle.debit, 3)
			consolidation_dict.total_credit += flt(gle.credit, 3)
			
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
				d.get("consolidation_code"),
				d.get("opening"),
				d.get("debit"), d.get("credit"), d.get("balance")
			])			
	else:
		for d in data:
			result.append([
				d.get("posting_date"),
				d.get("consolidation_code"),
				d.get("voucher_type"), d.get("voucher_no"),	
				d.get("party"),
				d.get("debit"), d.get("credit"), d.get("balance"),						
				d.get("party_type"), d.get("remarks")
			])
	return result