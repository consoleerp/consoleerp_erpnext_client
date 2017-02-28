cur_frm.add_fetch("consoleerp_territory", "consoleerp_abbr", "consoleerp_territory_abbr");

frappe.ui.form.on("Delivery Note", {
	refresh : function(frm) {
		frm.set_query("consoleerp_warehouse", function() {
			return {
				filters : { "consoleerp_territory" : cur_frm.doc.consoleerp_territory, "is_group" : 0 }
			}
		});		
		
		frm.set_query("warehouse", "items", function(doc, cdt, cdn) {
			return {
				filters : { "consoleerp_territory" : doc.consoleerp_territory, "is_group" : 0}
			}
		});
	},
	validate : function(frm) {
		frm.doc.territory = frm.doc.consoleerp_territory;
	},
	
	// setting warehouse = null on territory change
	consoleerp_territory : function(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "consoleerp_warehouse", null);
	},
	
	consoleerp_warehouse : function(frm, cdt, cdn) {
		$.each(frm.doc.items, function(i, child_doc){			
			frappe.model.set_value("Delivery Note Item", child_doc.name, "warehouse", frm.doc.consoleerp_warehouse);
		});
	}
});


frappe.ui.form.on('Delivery Note Item', {
	items_add : function(frm, cdt, cdn) {
		frappe.after_ajax(function() {
			frappe.model.set_value(cdt, cdn, "warehouse", frm.doc.consoleerp_warehouse);
		});
	},
	
	// cost + header warehouse
	item_code : function(frm, cdt, cdn) {		
		frappe.after_ajax(function() {
			frappe.model.set_value(cdt, cdn, "warehouse", frm.doc.consoleerp_warehouse);
	});
	}
});