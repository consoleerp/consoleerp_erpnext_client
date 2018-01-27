import click
import frappe
from frappe.commands import pass_context, get_site

@click.command("consoleerp")
@pass_context
@click.argument("cmd")#, help="Choose from [restore_google_drive]")
def consoleerp_commands(context, cmd):
	# init frappe before proceeding
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	if cmd == "restore_google_drive":
		
		from utils.google_drive import download_latest_client_backup
		download_latest_client_backup()
		
	else:
		print("Invalid Option")
	
	frappe.destroy()
	
commands = [consoleerp_commands]