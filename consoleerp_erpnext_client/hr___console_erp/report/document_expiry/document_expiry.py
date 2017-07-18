# Copyright (c) 2013, Console ERP and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data

def get_columns(filters):
	return [
		_("Doc No") + ":Data:100",
		_("Type") + ":Link/Document Type:80",
		_("Issue Date") + ":Date:80",
		_("Expiry Date") + ":Date:80",
		_("Place of Issue") + ":Data:120",
		_("Remarks") + ":Data:180"
	]
	
def get_data(filters):
	return frappe.db.sql("""
	SELECT
		doc.doc_no, doc.type, doc.issue_date, doc.expiry_date,
		doc.place_of_issue, doc.remarks
	FROM
		`tabDocument` doc,
		`tabDocument Type` doc_type
	WHERE
		doc.type = doc_type.name
		AND (date(`expiry_date`) BETWEEN %(from_date)s and %(to_date)s)
		AND doc_type.related_to = %(related_to)s
	""", filters)
