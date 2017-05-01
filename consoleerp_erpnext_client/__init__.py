# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe

__version__ = '1.0.0'

@frappe.whitelist()
def backup_to_google_drive():
	from consoleerp_erpnext_client.utils.google_drive import test
	test()