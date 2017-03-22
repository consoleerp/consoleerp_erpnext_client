cur_frm.add_fetch("consoleerp_territory", "consoleerp_abbr", "consoleerp_territory_abbr");

frappe.ui.form.on("Payment Entry",{
	onload : function(frm) {
				
		frappe.after_ajax(function() {
		
			if (frm.doc.references && frm.doc.references[0])
			{
				var ref = frm.doc.references[0];
				frappe.db.get_value(ref.reference_doctype, ref.reference_name, ["consoleerp_territory", "consoleerp_territory_abbr"], function(v) {					
					if (!v.consoleerp_territory)
						return;
					
					frappe.model.set_value("Payment Entry", frm.doc.name, "consoleerp_territory", v.consoleerp_territory);
					frappe.model.set_value("Payment Entry", frm.doc.name, "consoleerp_territory_abbr", v.consoleerp_territory_abbr);
				});
			}
		});
	}
});