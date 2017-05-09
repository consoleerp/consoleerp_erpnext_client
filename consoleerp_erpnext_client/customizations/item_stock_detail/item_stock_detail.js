frappe.ui.form.on(cur_frm.doctype, {
	setup : function(frm) {		
		document.addEventListener('keydown', keyDownEvent);
		
		function removeBind() {
			// remove item search
			document.removeEventListener('keydown', keyDownEvent, false);
			// remove this
			$(window).off('hashchange', removeBind);
		}
		
		// remove the keydown event and thisone
		$(window).on('hashchange', removeBind);
	}
});

function keyDownEvent(event) {
	var keyName = event.key;	
	if (keyName === "F4") {				
		if ($('.data-row.editable-row') != null){
			var current_doc = $('.data-row.editable-row').parent().attr("data-name");
			var doc = locals["Sales Invoice Item"][current_doc];
			
			if (doc.item_code == null)
				return;								
			frappe.call({
				"method" : "consoleerp_erpnext_client.api.item.item_warehouse_info",
				args : {
					"item" : doc.item_code					
				},
				callback : function(r) {					
					if (r.message == null)
						return;					
					
					if (r.message == "not_stock_item") {					
						show_alert(doc.item_name + " is not a stock Item");
						return;
					}
					
					var item_detail = "Stock Details for " + doc.item_code
								+ "<table class='table table-striped table-bordered'>"
										+ "<tr>"
												+ "<th width='30%'>Warehouse</th>" 
												+ "<th width='17.5%'>Reserved Qty</th>" 
												+ "<th width='17.5%'>Actual Qty</th>" 
												+ "<th width='17.5%'>Available Qty</th>"
												+ "<th width='17.5%'>Projected Qty</th>"												
										+"</tr>";
					
					$.each(r.message, function(i, obj) {
						item_detail += 
								"<tr>"
									+ "<td>" + obj.warehouse + "</td>"
									+ "<td>" + obj.reserved_qty + "</td>"
									+ "<td>" + obj.actual_qty + "</td>"
									+ "<td>" + obj.available_qty + "</td>"
									+ "<td>" + obj.projected_qty + "</td>"
							+	"</tr>"						
					});
					
					item_detail += "</table>"
							+ "<blockquote>"
								+	"Projected Qty = Actual Qty + Planned Qty + Requested Qty + Ordered Qty - Reserved Qty"
							+ "</blockquote>"
							+ "<ul>"
								+ "<li>Actual Qty: Quantity available in the warehouse.</li>"
								+ "<li>Planned Qty: Quantity, for which, Production Order has been raised, but is pending to be manufactured.</li>"
								+ "<li>Requested Qty: Quantity requested for purchase, but not ordered.</li>"
								+ "<li>Ordered Qty: Quantity ordered for purchase, but not received.</li>"
								+ "<li>Reserved Qty: Quantity ordered for sale, but not delivered.</li>"
							+ "</ul>"
					
					msgprint(item_detail, "Item Stock Detail");
				}
			});
		}
	}

}