from frappe import _

def get_date():
	return {
		
		'internal_links': {
			'Warehouse Transfer': ['items', 'reference_warehouse_transfer']
		},
		'transactions': [
			{
				'lablel': _('Related'),
				'items': ['Warehouse Transfer']
			}
		]
	}