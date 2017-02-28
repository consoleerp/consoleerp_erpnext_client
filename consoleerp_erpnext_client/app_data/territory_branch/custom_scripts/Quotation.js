cur_frm.add_fetch("consoleerp_territory", "consoleerp_abbr", "consoleerp_territory_abbr");

frappe.ui.form.on("Quotation", {
	validate : function(frm) {
		frm.doc.territory = frm.doc.consoleerp_territory;
	}
});