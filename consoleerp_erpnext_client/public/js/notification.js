$(document).on('startup', function(){
	// on startup
	if (!frappe.boot.consoleerp || frappe.get_route()[0] != "")
		return;

	if (frappe.boot.consoleerp.expiring_documents && frappe.boot.consoleerp.expiring_documents.length > 0) {
		var rows = frappe.boot.consoleerp.expiring_documents.reduce(function(str, obj){
			return str
			+ "<tr>"
				+ "<td>"+ obj.doc_no +"</td>"
				+ "<td>"+ obj.type +"</td>"
				+ "<td>"+ obj.expiry_date +"</td>"
				+ "<td>"
					+ "<a data-parent='"+obj.parent+"' data-parenttype='"+obj.parenttype+"'>"
						+ obj.parenttype
						+ "-"
						+ obj.parent
					+"</a>"
				+ "</td>"
			+ "</tr>";
		}, "");
		var $wrapper = frappe.msgprint("<h3>Expiring Documents</h3>"
							+ "<br>The following documents will expire soon."
							+ "<table class='table table-striped table-hover'>"
								+ "<thead>"
									+ "<tr>"
										+ "<th>" + __("Doc No") + "</th>"
										+ "<th>" + __("Type") + "</th>"
										+ "<th>" + __("Expiry Date") + "</th>"
										+ "<th>" + __("Parent") + "</th>"
									+ "</tr>"
								+ "</thead>"
								+ "<tbody>"
								+ rows
								+ "</tbody>"
							+ "</table>"
							+ "<hr>"
							, "Console ERP Notifications").$wrapper;
		$wrapper.find("a").on("click", function(){
			frappe.set_route("Form", $(this).data("parenttype"), $(this).data("parent"));
		})

		// show only once
		//frappe.boot.consoleerp.expiring_documents = null;
	}
});