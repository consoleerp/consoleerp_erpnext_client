import frappe

def convert_item_to_batched(item_code):
	"""
	-	how is batch defined ? where is the qty details of the batch stored ?
		where is it fetched ? and on move where is it taken ?
		--> no qty info stored in tabBatch
			everything from stock ledger
			
	- One batch per item ?
		yes

	- How is reference to an item tracked on deletion ?
		- check_if_doc_is_linked		`from frappe.model.rename_doc import get_link_fields(doctype)`
			-	parent doctype is obtained
				if doctype contains field batch_no:
					update;
					--> obtain field list
						`frappe.db.get_table(doctype)`
		- check_if_doc_is_dynamically_linked

	create new batch named 'x' for item y with total qty = total incoming qty
	total qty = sum(positive actual_qty from tabStock Ledger Entry)
	- no need to update the qtys anywhere
		all such details comes from stock ledger entries
	"""
	
	if frappe.db.get_value("Item", item_code, "has_batch_no"):
		print("Already batched item.")
		return
	
	frappe.db.begin()
	
	try:
		frappe.db.set_value("Item", item_code, "has_batch_no", 1)
		frappe.db.set_value("Item", item_code, "create_new_batch", 1)
		
		batch_doc = frappe.new_doc("Batch")
		temp = None
		while not temp:
			temp = frappe.generate_hash()[:7].upper()
			if frappe.db.exists("Batch", temp):
				temp = None
		
		batch_doc.batch_id = temp		
		batch_doc.item = item_code
		batch_doc.description = "Auto Generated - Console ERP Solutions"
		batch_doc.insert()
		
		# static links
		# ignoring dynamic links
		# refer frappe.model.delete_doc.check_if_doc_is_dynamically_linked
		from frappe.model.rename_doc import get_link_fields
		links = get_link_fields("Item")
		for link_field in links:
			if link_field.issingle:
				continue
			
			columns = frappe.db.get_table_columns(link_field.parent)
			
			if not "item_code" in columns or not "batch_no" in columns:
				continue
				
			frappe.db.sql("UPDATE `%s` SET batch_no=%s where item_code=%s;" % ('tab' + link_field.parent, "%s", "%s"),
					(batch_doc.batch_id, item_code), debug=1)
					
		
		frappe.db.sql("UPDATE `tabStock Ledger Entry` SET batch_no=%s WHERE item_code=%s;",
					(batch_doc.batch_id, item_code), debug=1)		
		
		from frappe.sessions import clear_cache
		
		print("Successfully converted")
	
	except Exception:
		frappe.db.rollback()
		raise
	else:
		frappe.db.commit()