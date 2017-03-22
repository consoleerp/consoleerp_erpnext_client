cur_frm.add_fetch("consoleerp_territory", "consoleerp_abbr", "consoleerp_territory_abbr");

frappe.ui.form.on("Stock Entry", {
	refresh : function(frm) {
		
		var source_lock = ["Material Issue", "Material Transfer"];
		var target_lock = ["Material Receipt"];
		var both_lock = ["Material Transfer for Manufacture", "Manufacture", "Repack", "Subcontract"];
		
		frm.set_query("from_warehouse", function(doc) {						
			if (source_lock.includes(frm.doc.purpose) || both_lock.includes(frm.doc.purpose))
			{
				return {
					filters : { "consoleerp_territory" : doc.consoleerp_territory }
				}
			} else 
			{
				return {}
			}
		});
		
		frm.set_query("to_warehouse", function(doc) {
			if (target_lock.includes(frm.doc.purpose) || both_lock.includes(frm.doc.purpose))
			{
				return {
					filters : { "consoleerp_territory" : doc.consoleerp_territory }
				}
			} else 
			{
				return {}
			}
		});
	}
});