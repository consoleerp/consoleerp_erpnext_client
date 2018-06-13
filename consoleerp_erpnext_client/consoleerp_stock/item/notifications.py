import itertools
from operator import itemgetter
import frappe
from erpnext.stock.doctype.batch.batch import get_batch_qty
from frappe.utils import DATE_FORMAT

def get_expiring_batch_notifications():
	
	message = ""
	
	# expiring batch
	notify_batch_expiration = frappe.db.get_value("ConsoleERP Settings", filters="*", fieldname="notify_batch_expiration")
	if not notify_batch_expiration:
		return ""	
	
	expiring_batches = frappe.db.sql("""
	SELECT
		batch.item, batch.name, batch.expiry_date
	FROM
		tabBatch batch, tabItem item
	where
		batch.item = item.name AND
		NOT batch.hide_expiry_notification AND
		item.notify_batch_expiration AND
		expiry_date < DATE_ADD(CURDATE(), INTERVAL COALESCE((IF(item.notify_expiration_before=0, NULL, item.notify_expiration_before)), (SELECT value from tabSingles where field='default_batch_expiration_days' and doctype='ConsoleERP Settings'), 90) DAY) order by expiry_date;
	""", as_dict=1)
	
	for x in expiring_batches:
		x["qty"] = 0
		qty_wh_list = get_batch_qty(x.name)
		for wh_obj in qty_wh_list:
			x.qty += wh_obj.qty
	
	expiring_batches = [x for x in expiring_batches if x.qty > 0]
	if not len(expiring_batches) > 0:
		return "";
	
	message += """<h3>Expiring Batches</h3>
	<table class='table table-bordered table-condensed table-hover table-responsive table-striped'>
		<thead>
			<th>Item</th>
			<th>Batch</th>
			<th>Expiry Date</th>
			<th>Batch Qty</th>
		</thead>
		<tbody>
	"""
	for item, values in itertools.groupby(expiring_batches, key=itemgetter('item')):
		# item - item code
		# values: grouped values
		values = list(values)
		message += """
		<tr>
			<td><a href='#Form/Item/{item}'>{item}</a>
			<td>{batch_reduce}</td>
			<td>{date_reduce}</td>
			<td>{qty_reduce}</td>
		</tr>
		""".format(**{
			"item": item,
			"batch_reduce": reduce(lambda x,y: x + ("<br>" if len(x) > 0 else "") + "<a href='#Form/Batch/{name}'>{name}</a>".format(**y), values, ""),
			"date_reduce": reduce(lambda x,y: x + ("<br>" if len(x) > 0 else "") + "{}".format(y.expiry_date.strftime(DATE_FORMAT)), values, ""),
			"qty_reduce": reduce(lambda x,y: x + ("<br>" if len(x) > 0 else "") + "{}".format(y.qty), values, "")
		})
	
	
	message += "</tbody></table>"
	return message