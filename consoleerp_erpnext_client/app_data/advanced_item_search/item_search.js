document.addEventListener('keydown', (event) => {		
	if (event.key == "F2"){
				
		dialog = new frappe.ui.Dialog({
			title: __("Select {0}", [(cur_frm.doctype=='[Select]') ? __("value") : __("Item")]),
			fields: [
				{
					fieldtype: "Data", fieldname: "txt", label: __("Beginning with"),
					description: __("You can use wildcard %"),
				},
				{
					fieldtype: "HTML", fieldname: "results"
				}
			],
			primary_action_label: __("Search"),
			primary_action: function() {
				search(this);
			}
		});

		dialog.get_input("txt").on("keyup", function(e) {
			// on enter press
			// if(e.which===13) ---- enter
			input_timeout(function(){
							search(dialog);
			}, 1000);			
		});
		dialog.show();
		search(dialog);
		
	}
}, false);


var search = function(dialog){
	
	var args = {
				txt: dialog.fields_dict.txt.get_value(),
				searchfield: "name"
			},
			me = this;

		frappe.link_search("Item", args, function(r) {
			var parent = dialog.fields_dict.results.$wrapper;
			parent.empty();
			if(r.values.length) {
				$.each(r.values, function(i, v) {
					var row = $(repl('<div class="row link-select-row">\
						<div class="col-xs-4">\
							<b><a href="#" style="hover:color:darkgray;">%(name)s</a></b></div>\
						<div class="col-xs-8">\
							<span class="text-muted">%(values)s</span></div>\
						</div>', {
							name: v[0],
							values: v.splice(1).join(", ")
						})).appendTo(parent);

					row.find("a")
						.attr('data-value', v[0])
						.click(function() {
						var value = $(this).attr("data-value");

						// on click of item
						// if first item is empty--
						var cdn = cur_frm.doctype + " Item"; // Sales Invoice Item, Sales Order Item
						if (cur_frm.doc.items.length > 0 && !cur_frm.doc.items[cur_frm.doc.items.length-1].item_code)
						{
							frappe.model.set_value(cdn, cur_frm.doc.items[cur_frm.doc.items.length-1].name, "item_code", value);
						} 
						else 
						{
							var child_doc = frappe.model.add_child(cur_frm.doc, cdn, "items");
							frappe.model.set_value(cdn, child_doc.name, "item_code", value);
						}
						
						dialog.hide();
						
						return false;
					})
				})
			} else {
				$('<p><br><span class="text-muted">' + __("No Results") + '</span>'
					+ (frappe.model.can_create(me.doctype) ?
						('<br><br><a class="new-doc btn btn-default btn-sm">'
						+ __("Make a new {0}", [__(me.doctype)]) + "</a>") : '')
					+ '</p>').appendTo(parent).find(".new-doc").click(function() {
						me.target.new_doc();
					});
			}
		}, dialog.get_primary_btn());
}

// timeout function for keyinput
var input_timeout = (function(){
  var timer = 0;
  return function(callback, ms){
    clearTimeout (timer);
    timer = setTimeout(callback, ms);
  };
})();

frappe.link_search = function(doctype, args, callback, btn) {
	if(!args) {
		args = {
			txt: ''
		}
	}
	args.doctype = doctype;
	if(!args.searchfield) {
		args.searchfield = 'name';
	}

	frappe.call({
		method: "frappe.desk.search.search_widget",
		type: "GET",
		args: args,
		callback: function(r) {
			callback && callback(r);
		},
		btn: btn
	});
}