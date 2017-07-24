# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
import consoleerp_erpnext_client.hr___console_erp

__version__ = '1.0.0'
	
def queue_doc_submit(doctype, name):
	doc = frappe.get_doc(doctype, name)
	if doc.docstatus == 1:
		print("This document is already submitted")
	else:
		doc.queue_action('submit')

def boot_session(bootinfo):		
	bootinfo.consoleerp = {
		"expiring_documents": get_expiring_documents()
	}
	return bootinfo
	