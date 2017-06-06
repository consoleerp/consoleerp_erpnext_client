// app_included js file
// used for global checks

// the following two handles will watch the page changes everywhere
$(window).on('hashchange', page_changed);
$(window).on('load', page_changed);

function page_changed(event) {
	
	// waiting for page to load completely
	frappe.after_ajax(function() {
	
		var route = frappe.get_route();	
		
		// backup button
		if (route[0] === "backups") {
			// add 'Take backup now' button			
			frappe.ui.pages["backups"].add_inner_button(__("Take Backup Now"), function() {
				
				// freeze window
				frappe.dom.freeze("Please Wait");
				
				// frappe call
				frappe.call({
					method: "consoleerp_erpnext_client.utils.system.take_backup",
					callback: function(r) {
						if (r.message) {
							console.log(r.message);
							var $wrapper = frappe.msgprint(																		
											"Download the backup files using the links provided:"
											+ "<table class='table table-striped table-bordered'>"
													+ "<tr>"
														+ "<th width='20%'>File</th>"
														+ "<th width='60%'>Description</th>"
														+ "<th width='20%'>Download</th>"
													+ "</tr>"
													+ "<tr>"
														+ "<td>Database</td>"
														+ "<td>Contains the database only</td>"
														+ "<td><a href='" + r.message.db + "'><u>Download</u></a></td>"
													+ "</tr>"
													+ "<tr>"
														+ "<td>Public Files</td>"
														+ "<td>Files that anybody can access.<br>For eg: Letter Head Images</td>"
														+ "<td><a href='" + r.message.files + "'><u>Download</u></a></td>"
													+ "</tr>"
													+ "<tr>"
														+ "<td>Private Files</td>"
														+ "<td>Files that authorized users can access.<br>For eg: Copy of Supplier Invoice attached to a purchase document.</td>"
														+ "<td><a href='" + r.message.private_files + "'><u>Download</u></a></td>"
													+ "</tr>"
											+ "</table>"
											+ "<hr>"
											+ "<div class='text-center'>"
												+ "<button id='download_single_file' data-backup_name='"+r.message.backup_name+"' class='btn btn-default btn-sm'>Download Compressed File</button>"
											+ "</div>"
											, "Backup Successful").$wrapper;
											
							$wrapper.find('#download_single_file').on('click', function(event) {								
								var backup_name = $(this).data("backup_name");
								
								// frappe call zip function
								frappe.call({
									method: "consoleerp_erpnext_client.utils.system.zip_and_download_files",
									args: {
										filename: backup_name,
										files: r.message.abs_paths
									},
									callback: function(r) {
										if (r.message) {											
											window.location.href = r.message;
										}
									}
								});
							});
						} else {
							show_alert("Backup failed.")
						}
						frappe.dom.unfreeze();
					}
				});
			});
		}
	});
}


// call this with an async function
function sleep_for_ms(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
