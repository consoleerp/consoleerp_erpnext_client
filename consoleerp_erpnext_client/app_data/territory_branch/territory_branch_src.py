import frappe, os
from frappe.core.page.data_import_tool.data_import_tool import import_doc

@frappe.whitelist()
def setup():
	""" 
		- Imports Custom_Field.csv
		- Import all the scripts in custom_scripts
	"""
	data_path = frappe.get_app_path("consoleerp_erpnext_client", "app_data", "territory_branch")
	
	if os.path.exists(data_path):
		
		# import Custom_Field.csv
		import_doc(data_path + os.path.sep + "Custom_Field.csv", ignore_links=True, overwrite=True)
		
		for fname in os.listdir(data_path + os.path.sep + "custom_scripts"):
			if fname.endswith(".js"):
				with open(data_path + os.path.sep + "custom_scripts" + os.path.sep + fname) as f:
					doctype = fname.rsplit(".", 1)[0]
					script = f.read()
					if frappe.db.exists("Custom Script", {"dt" : doctype}):
						custom_script = frappe.get_doc("Custom Script", {"dt" : doctype})
						custom_script.script = "%s\n\n// Custom Script from Console ERP ERPNext Client\n%s" % (custom_script.script, script)
						custom_script.save()
					else:
						frappe.get_doc({
							"doctype" : "Custom Script",
							"dt" : doctype,
							"script_type" : "Client",
							"script" : script
						}).insert()
		
		return "1";