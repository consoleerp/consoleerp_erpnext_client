// Console ERP Solutions

frappe.query_reports["Consolidated Statement of Account"] = {
	"filters": [
		{
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"reqd": 1
		},
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 1,
			"width": "60px"
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
			"width": "60px"
		},
		{
			"fieldname":"consolidation_code",
			"label": __("Consolidation Code"),
			"fieldtype": "Link",
			"options": "Consolidation",
			"default": ""
		},
		{
			"fieldname":"summary_report",
			"label": __("Summary Report"),
			"fieldtype": "Check",
			"default": 1
		}
	]
}