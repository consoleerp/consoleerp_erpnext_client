import frappe
import frappe.utils

def get_expiring_documents():
	expiring_docs = []
	for document_type in frappe.get_all('Document Type', fields=["name", "related_to", "alert_before"]):
		# get documents expiring for this type				
		expiry_date = frappe.utils.add_to_date(frappe.utils.now_datetime(), \
						days=-1*(document_type.alert_before or 14), as_string=True)
		for expiring_doc in frappe.get_all('Document', filters={"type": document_type.name, "expiry_date": [">=", expiry_date]},\
						fields=['name', 'doc_no', 'type', 'expiry_date', 'parent', 'parenttype']):
			expiring_docs.append(expiring_doc)
	return expiring_docs