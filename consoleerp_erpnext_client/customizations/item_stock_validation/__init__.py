import frappe
from frappe import _
from consoleerp_erpnext_client.api.item import item_warehouse_info

@frappe.whitelist()
def validate(self, method):
	"""
	Validates if the item has enough stock
	"""
	settings = frappe.get_doc("ConsoleERP Settings", None)
	if not settings.item_stock_validate_on in ["Input", "Save", "Submit"] or not self.update_stock:
		return	
	
	qty_string = (settings.item_stock_compare_with.replace(" ", "_")).lower()	
	msgs = []
	for i, d in enumerate(self.items):
		
		# actual qty is retuned if posting date and time is passed
		inf = item_warehouse_info(d.item_code, d.warehouse, self.posting_date, self.posting_time)		
		# is returned not_stock_item when its not
		if inf == "not_stock_item":
			continue		
					
		inf_qty = inf or 0		
		# V8
		if d.qty > (inf_qty / d.conversion_factor):
			msg = _("Row: {4} - Not enough stock for {0} in warehouse {1}. {2} is {3}").format(d.item_code, d.warehouse, "Actual Qty", inf_qty, i + 1)			
			msgs.append(msg)
	
	if msgs:
		if settings.item_stock_throw_type == "Prevent Saving":
			frappe.throw("<br>".join(msgs))
		else:
			frappe.msgprint("<br>".join(msgs))