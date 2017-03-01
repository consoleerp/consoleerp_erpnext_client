cur_frm.add_fetch("consoleerp_territory", "consoleerp_abbr", "consoleerp_territory_abbr");

frappe.ui.form.on("Payment Request",{
	onload : function(frm) {
				
		frappe.after_ajax(function() {
		
			if (frm.doc.reference_name)
			{				
				frappe.db.get_value(frm.doc.reference_doctype, frm.doc.reference_name, ["consoleerp_territory", "consoleerp_territory_abbr"], function(v) {					
					if (!v.consoleerp_territory)
						return;
					
					frappe.model.set_value("Payment Request", frm.doc.name, "consoleerp_territory", v.consoleerp_territory);
					frappe.model.set_value("Payment Request", frm.doc.name, "consoleerp_territory_abbr", v.consoleerp_territory_abbr);
				});
			}
		});
	}
});