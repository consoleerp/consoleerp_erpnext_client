# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "consoleerp_erpnext_client"
app_title = "ConsoleERP ERPNext Client"
app_publisher = "Console ERP"
app_description = "Provides tools to implement at customer site"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "info@consoleerp.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/consoleerp_erpnext_client/css/consoleerp_erpnext_client.css"
# app_include_js = "/assets/consoleerp_erpnext_client/js/consoleerp_erpnext_client.js"
app_include_js = "/assets/js/consoleerp.min.js"
boot_session = "consoleerp_erpnext_client.config.boot_session"

# include js, css files in header of web template
# web_include_css = "/assets/consoleerp_erpnext_client/css/consoleerp_erpnext_client.css"
# web_include_js = "/assets/consoleerp_erpnext_client/js/consoleerp_erpnext_client.js"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "consoleerp_erpnext_client.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "consoleerp_erpnext_client.install.before_install"
# after_install = "consoleerp_erpnext_client.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "consoleerp_erpnext_client.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }
doctype_js = {
	"Employee": "doctype_js/employee.js",
	"Vehicle": "doctype_js/vehicle.js"
}

# Scheduled Tasks
# ---------------
scheduler_events = {
	"daily": [
		"consoleerp_erpnext_client.utils.google_drive.upload_backup"
	]
}
# scheduler_events = {
# 	"all": [
# 		"consoleerp_erpnext_client.tasks.all"
# 	],
# 	"daily": [
# 		"consoleerp_erpnext_client.tasks.daily"
# 	],
# 	"hourly": [
# 		"consoleerp_erpnext_client.tasks.hourly"
# 	],
# 	"weekly": [
# 		"consoleerp_erpnext_client.tasks.weekly"
# 	]
# 	"monthly": [
# 		"consoleerp_erpnext_client.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "consoleerp_erpnext_client.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "consoleerp_erpnext_client.event.get_events"
# }
fixtures = [
{
	"dt": "Property Setter",
	"filters": [
		["name", "in", [
			"Sales Invoice Payment-amount-depends_on"			# Sales Return
		]]
	]
},
{
	"dt": "Custom Field",
	"filters": [
		["name", "in", [
		
			# Batch Expiry Notifications
			"Item-notifications",
			"Item-notify_batch_expiration",
			"Item-notify_expiration_before",
			"Batch-hide_expiry_notification"
		]]
	]
}]

