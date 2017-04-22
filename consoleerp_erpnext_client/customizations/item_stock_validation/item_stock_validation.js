/*
*	item_stock_validate_on -- None, Save, Input
*	item_stock_qty_correction_type -- Set to 0, Do Not Change
*	item_stock_throw_type -- Prevent Saving, Warning
*	item_stock_compare_with -- Actual Qty, Projected Qty, Available Qty
*
*	`Input` validation is done here
*			(checking when each row is entered)
*	`Save` validation is done on the server side. 
*			(attach it via hooks)
*/
var item_stock;

frappe.ui.form.on(cur_frm.doctype, {
	onload: function(frm) {
		
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "ConsoleERP Settings",
				fieldname: ["item_stock_validate_on", "item_stock_qty_correction_type", "item_stock_throw_type", "item_stock_compare_with"],
				filters: "*"
			},
			callback: function(r) {
				if (r.message) {
					item_stock = r.message;
					frm.events.init();
				}
			}
		});
	},
	
	init: function() {	
		
		// if only stock is checked as its being entered
		if (item_stock.item_stock_validate_on == "Input")
			frappe.ui.form.on(cur_frm.fields_dict["items"].grid.doctype, {
				qty: function(frm, cdt, cdn) {
					var d = locals[cdt][cdn];
					validate_item_stock(d);
				},
				warehouse: function(frm, cdt, cdn) {
					var d = locals[cdt][cdn];
					validate_item_stock(d);
				}
			}); 
	}
});

var validate_item_stock = function(child_doc) {
	if (!child_doc.item_code || !child_doc.warehouse)
		return;
	
	frappe.after_ajax(function() {
		frappe.call({
			method: "consoleerp_erpnext_client.api.item.item_warehouse_info",
			args: {
				item: child_doc.item_code,
				warehouse: child_doc.warehouse
			},
			callback: function(r) {
				if (r.message) {
					var compare_qty;
					switch(item_stock.item_stock_compare_with) {
						case "Actual Qty":
							compare_qty = r.message[0].actual_qty;
						break;
						case "Projected Qty":
							compare_qty = r.message[0].projected_qty;
						break;
						case "Available Qty":
							compare_qty = r.message[0].available_qty;
						break;
					}

					// V8
					// change to stock_qty
					if (child_doc.qty > compare_qty) {
						if (item_stock.item_stock_qty_correction_type === "Set to 0") {
							frappe.msgprint("Not enough stock for "+ child_doc.item_code +" in warehouse "+ child_doc.warehouse +". Qty available is " + compare_qty);
							frappe.model.set_value(child_doc.doctype, child_doc.name, "qty", 0);
						} else {
							show_alert("Not enough stock for "+ child_doc.item_code +" in warehouse "+ child_doc.warehouse +". Qty available is " + compare_qty);
						}
					}
				}
			}
		});
	});
}