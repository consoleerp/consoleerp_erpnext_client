import frappe

@frappe.whitelist()
def item_warehouse_info(item, warehouse=None):
	if not frappe.db.get_value("Item", item, "is_stock_item"):
		return "not_stock_item"

	if not warehouse:
		return frappe.db.sql("select warehouse, valuation_rate, actual_qty from tabBin where item_code = '"+ item +"';", as_dict=True)
	else:
		return frappe.db.sql("select valuation_rate, actual_qty from tabBin where item_code = '"+ item +"' and warehouse = '"+warehouse+"';", as_dict=True)
