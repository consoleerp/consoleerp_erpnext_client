## Item Stock Validation

Validates if the current item has enough stock.
Settings are specified in `ConsoleERP Settings`

	item_stock_validate_on -- None, Save, Input
	item_stock_qty_correction_type -- Set to 0, Do Not Change (visible only if validate_on = `Input`)
	item_stock_throw_type -- Prevent Saving, Warning
	item_stock_compare_with -- Actual Qty, Projected Qty, Available Qty

	`Input` validation is done on the client side. frappe calls `consoleerp_erpnext_client.api.item.item_warehouse_info`
			(checking when each row is entered)
	`Save` validation is done on the server side. 
			(attach it via hooks)

Include the `item_stock_validation.js` file
and call the python validate method from the DocType custom python file