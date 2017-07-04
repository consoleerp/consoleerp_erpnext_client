import frappe, os
from frappe.core.page.data_import_tool.data_import_tool import import_doc

@frappe.whitelist()
def setup():
	""" 
		- Imports Custom_Field.csv
		- Import all the scripts in custom_scripts
	"""
	data_path = frappe.get_app_path("consoleerp_erpnext_client", "customizations", "territory_branch")

	# naming series data 
	naming_series_data = {
		"Quotation" : ["QTN-.consoleerp_territory_abbr.-"],
		"Sales Order" : ["SO-.consoleerp_territory_abbr.-"],
		"Delivery Note" : ["DN-.consoleerp_territory_abbr.-", "DN-RET-.consoleerp_territory_abbr.-"],
		"Sales Invoice" : ["SINV-.consoleerp_territory_abbr.-", "SINV-RET-.consoleerp_territory_abbr.-"],
		
		"Material Request" : ["MREQ-.consoleerp_territory_abbr.-"],
		"Request for Quotation" : ["RFQ-.consoleerp_territory_abbr.-"],
		"Supplier Quotation" : ["SQTN-.consoleerp_territory_abbr.-"],
		"Purchase Order" : ["PO-.consoleerp_territory_abbr.-"],
		"Purchase Receipt" : ["PREC-.consoleerp_territory_abbr.-", "PREC-RET-.consoleerp_territory_abbr.-"],
		"Purchase Invoice" : ["PINV-.consoleerp_territory_abbr.-", "PINV-RET-.consoleerp_territory_abbr.-"],
		
		"Stock Entry" : ["STE-.consoleerp_territory_abbr.-"],
		"Warehouse Transfer": ["WT-.consoleerp_territory_abbr.-"],
		"Payment Request" : ["PR-.consoleerp_territory_abbr.-"],
		"Payment Entry" : ["PE-.consoleerp_territory_abbr.-"]
	}
	
	if os.path.exists(data_path):
		
		# import Custom_Field.csv
		import_doc(data_path + os.path.sep + "Custom_Field.csv", ignore_links=True, overwrite=True)
		
		"""
		# import custom scripts-------------------------------
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
		"""
		
		# --------------------------------------------------------------------------
		# import naming series
		for doctype in naming_series_data:
			# update in property setter
			prop_dict = {'options': "\n".join(naming_series_data[doctype]), 'default': naming_series_data[doctype][0]}
			print doctype

			for prop in prop_dict:
				ps_exists = frappe.db.get_value("Property Setter",
					{"field_name": 'naming_series', 'doc_type': doctype, 'property': prop})

				if ps_exists:
					ps = frappe.get_doc('Property Setter', ps_exists)
					ps.value = prop_dict[prop]
					ps.save()
				else:
					ps = frappe.get_doc({
						'doctype': 'Property Setter',
						'doctype_or_field': 'DocField',
						'doc_type': doctype,
						'field_name': 'naming_series',
						'property': prop,
						'value': prop_dict[prop],
						'property_type': 'Text',
						'__islocal': 1
					})
					ps.save()
			
		
		return "1";


def has_permission(doc, ptype, user):
	"""
	create
	submit
	read
	write
	Currently everything under one-perm
	"""
	if user == "Administrator" or user == "su@consoleerp.com": return True

	from frappe.defaults import get_user_permissions
	user_permissions = get_user_permissions(user)

	return doc.consoleerp_territory in user_permissions.get('Territory', [])

def permission_query_conditions(user):
	if user == "Administrator" or user == "su@consoleerp.com": return "1=1"

	from frappe.defaults import get_user_permissions
	user_permissions = get_user_permissions(user)
	"','".join(user_permissions.get('Territory', []))
	return "(consoleerp_territory in ('{}'))".format("','".join(user_permissions.get('Territory', [])))