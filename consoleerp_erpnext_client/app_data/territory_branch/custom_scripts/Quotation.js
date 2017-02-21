frappe.ui.form.on("Quotation", {
	validate : function(frm) {
		frm.doc.territory = frm.doc.consoleerp_territory;
	}
});