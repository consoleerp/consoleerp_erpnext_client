from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Stock Transactions"),
			"items": [
				{
					"type": "doctype",
					"name": "Warehouse Transfer",
					"description": _("Transfer Items between Warehouses.")
				}
			]
		}
	]
