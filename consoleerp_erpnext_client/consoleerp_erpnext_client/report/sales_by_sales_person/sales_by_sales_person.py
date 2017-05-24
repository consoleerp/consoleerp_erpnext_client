# Copyright (c) 2013, Console ERP and contributors
# For license information, please see license.txt
#print("\n\n\n\n======================")		
#print("=======================\n\n\n\n")
from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
	validate_filters(filters)
	columns, data = get_columns(filters), get_data(filters)
	return columns, data

def validate_filters(filters):
	if not filters.get('company'):
		frappe.throw(_('{0} is mandatory').format(_('Company')))

def get_columns(filters):
	"""
	If summary_report:
		Sales Person, Gross, Discount, Net, Profit, Profit %
	else:
		Date, Sales Person, [DocType], Customer, Gross, Discount, Net, profit, profit %, Territory 
	"""
	if filters.get('summary_report'):
		return [
			_("Sales Person") + ":Link/"+_("Sales Person")+":160",
			_("Gross Total") + ":Float:100",	_("Discount") + ":Float:100", _("Net Total") + ":Float:100",
			_("Profit") + ":Float:100", _("Profit %") + ":Percent:100"
		]
	else:
		return [
			_("Posting Date") + ":Date:90",			
			_("Sales Person") + ":Link/"+_("Sales Person")+":160",
			_(filters.get('doctype')) + ":Link/"+_(filters.get('doctype'))+":130",
			_("Customer") + ":Link/"+_("Customer")+":160",
			_("Gross Total") + ":Float:100",	_("Discount") + ":Float:100", _("Net Total") + ":Float:100",
			_("Profit") + ":Float:100", _("Profit %") + ":Percent:100",
			_("Territory") + ":Link/"+_("Territory")+":160"
		]
	
def get_date_as_list(data_dict, filters):
	result = []
	if filters.get('summary_report'):
		for sales_person, sp_dict in data_dict.items():
			result.append([
					sales_person,
					sp_dict.gross_total,
					sp_dict.discount, sp_dict.net_total, 
					sp_dict.profit, sp_dict.profit_percentage
				])
	else:
		for sales_person, sp_dict in data_dict.items():
			for document, dt_dict in sp_dict.documents.items():
				result.append([
					dt_dict.posting_date,
					sales_person,
					dt_dict.name,
					dt_dict.customer,
					dt_dict.gross_total,
					dt_dict.discount, dt_dict.net_total, 
					dt_dict.profit, dt_dict.profit_percentage,
					dt_dict.territory
				])			
	return result
	
def get_data(filters):
	date_field = filters["doctype"] == "Sales Order" and "transaction_date" or "posting_date"
	conditions, values = get_conditions(filters, date_field)
	
	data = frappe.db.sql("""
	select
		dt.name, dt.customer, dt.territory, dt.%s as posting_date, dt.rounded_total,
		dt_item.item_code, dt_item.stock_qty, dt_item.warehouse, dt_item.base_price_list_rate, dt_item.base_net_amount,
		st.sales_person, st.allocated_percentage,
		dt_item.base_net_amount*st.allocated_percentage/100 as contribution_amt
	from
		`tab%s` dt, `tab%s Item` dt_item, `tabSales Team` st
	where
		st.parent = dt.name and dt_item.parent = dt.name and st.parenttype = %s
		and dt.docstatus = 1 %s order by st.sales_person, dt.name desc
	""" % (date_field, filters["doctype"], filters["doctype"], '%s', conditions),
				tuple([filters["doctype"]] + values), as_dict=1)
				
	data_dict = {}
	for row in data:
		sp_dict = data_dict.setdefault(row.sales_person, frappe._dict({
								'documents': frappe._dict(),
								'gross_total': 0,
								'discount' : 0,
								'net_total': 0,
								'cost': 0,
								'profit': 0,
								'profit_percentage': 0
							}))
		if filters.get('summary_report') and row.name not in sp_dict.documents.keys():
			# add formal net and gross (item discount not included)
			sp_dict.net_total += row.rounded_total			
			sp_dict.gross_total += row.rounded_total
			
		dt_dict = sp_dict.documents.setdefault(row.name, frappe._dict({
								'name': row.name,
								'posting_date': row.posting_date,
								'customer': row.customer,
								'territory' : row.territory,
								'gross_total': row.rounded_total,
								'discount': 0,								
								'net_total': row.rounded_total,
								'cost': 0,
								'profit' : 0,
								'profit_percentage': 0
							}))
		
		# add cost of the item,
		# get row-wise discount and add	
		discount_amount = (row.base_price_list_rate * row.stock_qty) - row.base_net_amount
		cost = get_cost_on_date(row.item_code, row.warehouse, row.posting_date) \
									* row.stock_qty
									
		if filters.get('summary_report'):
			# sales man details
			sp_dict.discount += discount_amount
			sp_dict.gross_total += discount_amount
			sp_dict.cost += cost
		else:
			# document details
			dt_dict.discount += discount_amount		
			dt_dict.gross_total += discount_amount		
			dt_dict.cost += cost
			
	
	for sales_person, sp_dict in data_dict.items():			
		if filters.get('summary_report'):
			sp_dict.profit = sp_dict.net_total - sp_dict.cost
			sp_dict.profit_percentage = sp_dict.profit * 100 / sp_dict.net_total
		else:
			for document, dt_dict in sp_dict.documents.items():
				dt_dict.profit = dt_dict.net_total - dt_dict.cost
				dt_dict.profit_percentage = dt_dict.profit * 100 / dt_dict.net_total
			
	return get_date_as_list(data_dict, filters)
	
def get_conditions(filters, date_field):
	conditions = [""]
	values = []

	for field in ["company", "customer", "territory"]:
		if filters.get(field):
			conditions.append("dt.{0}=%s".format(field))
			values.append(filters[field])

	if filters.get("sales_person"):
		lft, rgt = frappe.get_value("Sales Person", filters.get("sales_person"), ["lft", "rgt"])
		conditions.append("exists(select name from `tabSales Person` where lft >= {0} and rgt <= {1} and name=st.sales_person)".format(lft, rgt))

	if filters.get("from_date"):
		conditions.append("dt.{0}>=%s".format(date_field))
		values.append(filters["from_date"])

	if filters.get("to_date"):
		conditions.append("dt.{0}<=%s".format(date_field))
		values.append(filters["to_date"])

	return " and ".join(conditions), values
	
def get_cost_on_date(item_code, warehouse, posting_date):
	return (frappe.db.sql("""
		select
			incoming_rate
		from
			`tabStock Ledger Entry`
		where
			item_code=%s and warehouse=%s and posting_date<=%s
			and incoming_rate > 0 limit 1
	""", (item_code, warehouse, posting_date)) or ((0,),))[0][0]
	# find a better way to handle nulls