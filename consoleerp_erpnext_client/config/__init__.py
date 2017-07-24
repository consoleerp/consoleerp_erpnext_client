import frappe
from consoleerp_erpnext_client.hr___console_erp import get_expiring_documents

def boot_session(bootinfo):		
	bootinfo['consoleerp'] = {
		"expiring_documents": get_expiring_documents()
	}
	return bootinfo