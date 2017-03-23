import frappe

@frappe.whitelist()
def item_warehouse_info(item, warehouse=None):
	"""
	Returns the item details for the specified item-warehouse pair
	if warehouse is not specified, it will bring back the data from all the warehouses
	Item A
		- Warehouse A val_rate, qty's--
		- Warehouse B val_rate, qty's
		
	!! Data is fetched from Bins
	Data is returned as dicts
	"""
	
	# doc : https://frappe.github.io/frappe/current/api/frappe.database#get_value
	# if is not stock item, return error
	if not frappe.db.get_value("Item", item, "is_stock_item"):
		return "not_stock_item"

	# actualy_qty -- qty physically present at store (includes qty that is yet to be delivered)
	if not warehouse:
		return frappe.db.sql("select warehouse, valuation_rate, actual_qty, planned_qty, indented_qty, ordered_qty, reserved_qty, reserved_qty_for_production, projected_qty from tabBin where item_code = '"+ item +"';", as_dict=True)
	else:
		return frappe.db.sql("select valuation_rate, actual_qty, planned_qty, indented_qty, ordered_qty, reserved_qty, reserved_qty_for_production, projected_qty from tabBin where item_code = '"+ item +"' and warehouse = '"+warehouse+"';", as_dict=True)
