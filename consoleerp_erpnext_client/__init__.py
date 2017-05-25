# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

__version__ = '1.0.0'

@frappe.whitelist()
def backup_to_google_drive():
	from consoleerp_erpnext_client.utils.google_drive import test
	test()
	
def queue_doc_submit(doctype, name):
	doc = frappe.get_doc(doctype, name)
	if doc.docstatus == 1:
		print("This document is already submitted")
	else:
		doc.queue_action('submit')