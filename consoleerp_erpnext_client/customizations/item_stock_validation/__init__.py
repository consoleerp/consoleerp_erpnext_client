import frappe
from frappe import _
from consoleerp_erpnext_client.api.item import item_warehouse_info

@frappe.whitelist()
def validate(self, method):
	"""
	Validates if the item has enough stock
	"""
	settings = frappe.get_doc("ConsoleERP Settings", None)
	if not settings.item_stock_validate_on in ["Input", "Save"] or not self.update_stock:
		return	
	
	qty_string = (settings.item_stock_compare_with.replace(" ", "_")).lower()
	
	for d in self.items:
		inf = item_warehouse_info(d.item_code, d.warehouse)[0] or {}
		# is returned not_stock_item when its not
		if inf == "not_stock_item":
			continue
		
		# V8
		if d.qty > inf[qty_string]:
			msg = _("Not enough stock for {0} in warehouse {1}. {2} is {3}").format(d.item_code, d.warehouse, settings.item_stock_compare_with, inf[qty_string] or 0)
			if settings.item_stock_throw_type == "Prevent Saving":
				frappe.throw(msg)
			else:
				frappe.msgprint(msg)