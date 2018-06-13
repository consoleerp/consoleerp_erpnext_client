import frappe
from consoleerp_erpnext_client.hr___console_erp import get_expiring_documents
from consoleerp_erpnext_client.consoleerp_stock.item.notifications import get_expiring_batch_notifications

def boot_session(bootinfo):		
	bootinfo["consoleerp"] = {
		"expiring_documents": get_expiring_documents()
	}
	
	# startup messages
	
	# keep existing messages
	if "messages" in bootinfo and not isinstance(bootinfo["messages"], list):
		bootinfo["messages"] = [bootinfo["messages"]]
	bootinfo["messages"] = bootinfo.get("messages", [])
	
	bootinfo["messages"].append(get_expiring_batch_notifications())
	
	return bootinfo