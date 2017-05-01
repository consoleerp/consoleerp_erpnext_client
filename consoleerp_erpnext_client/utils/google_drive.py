import frappe
import httplib2
import os

from apiclient import discovery
from apiclient.http import MediaFileUpload
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

SCOPES = 'https://www.googleapis.com/auth/drive.file'
CLIENT_SECRET_FILE = '/home/consoleadmin/consoleerp/google_drive/client_secret.json'
APPLICATION_NAME = 'Console ERP Data Backup'

def upload_backup():

	credentials = get_credentials()
	http = credentials.authorize(httplib2.Http())
	drive_service = discovery.build('drive', 'v3', http=http)
	
	client_folder_id = get_client_folder_id(drive_service)
	print "client Folder: %s" % client_folder_id
	
	# backup data
	from frappe.utils.backups import BackupGenerator
	odb = BackupGenerator(frappe.conf.db_name, frappe.conf.db_name,\
						  frappe.conf.db_password, db_host = frappe.db.host)
	# older than is not applicable since its forced
	odb.get_backup(older_than=1, ignore_files=False, force=True)	
	print "Backup Successful : %s" % os.path.abspath(odb.backup_path_db)
	
	today_folder_id = get_today_folder_id(drive_service, client_folder_id)
	
	for filepath in [os.path.abspath(odb.backup_path_db), os.path.abspath(odb.backup_path_private_files ), os.path.abspath(odb.backup_path_files )]:
		filename = os.path.basename(filepath)
		response = drive_service.files().create(body={'name': filename, 'parents': [today_folder_id]}, fields="id", media_body=MediaFileUpload(filepath)).execute()
		print "Uploaded %s : %s" % (filename, response.get("id"))
	
def get_client_folder_id(drive_service):
	"""
	Returns the client folder to take the backups
	TODO fetch client name
	"""
	client_name = frappe.db.get_value("ConsoleERP Settings", filters="*", fieldname="client_name")
	print client_name
	
	response = drive_service.files().list(q="name = '%s' and mimeType='application/vnd.google-apps.folder'" % client_name, pageSize=1,
														fields='nextPageToken, files(id, name)').execute()
	for file in response.get("files", []):
		return file.get("id")		
	
	# client folder doesnt exist. creating folder	
	file = drive_service.files().create(body={ 'name': client_name, 'mimeType': 'application/vnd.google-apps.folder'},
																	fields="id").execute()	
	print "Folder Created. ID: %s" % file.get("id")
	
	return file.get("id")	
	
def get_today_folder_id(drive_service, client_folder_id):
	"""
	Get the id of todays folder under the current client
	Creates new if doesnt exist
	"""
	from frappe.utils import now_datetime
	today_folder_name = now_datetime().strftime('%d-%m-%Y')
	# check if folder exists, else create
	response = drive_service.files().list(q="name = '"+ today_folder_name
	+"' and mimeType='application/vnd.google-apps.folder' and '"+client_folder_id+"' in parents", pageSize=1,
														fields='nextPageToken, files(id, name)').execute()
	for file in response.get("files", []):
		return file.get("id")		
			
	response = drive_service.files().create(body={'name': today_folder_name, 'mimeType': 'application/vnd.google-apps.folder',
																		'parents': [client_folder_id]}, fields="id").execute()
	return response.get("id")

def list_all_files(drive_service):
	"""
	Lists all fiels created or opened by this app. This is the scope of this app
	"""
	results = drive_service.files().list(pageSize=10,fields="nextPageToken, files(id, name)").execute()
	items = results.get('files', [])
	if not items:
		print('No files found.')
	else:
		print('Files:')
		for item in items:
			print('{0} ({1})'.format(item['name'], item['id']))

def get_credentials():
	"""Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
	
	home_dir = os.path.expanduser('~')
	# details are always stored here, not on Github
	drive_dir = os.path.join(home_dir, 'consoleerp/google_drive')	
	credential_path = os.path.join(drive_dir, 'drive-consoleerp.json')
	
	store = Storage(credential_path)
	credentials = store.get()
	if not credentials or credentials.invalid:
		# have to get the flags. --noauth_local_webserver since we are not running javascript
		import argparse		
		flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args('--auth_host_name localhost --logging_level INFO --noauth_local_webserver'.split())		
		
		flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
		flow.user_agent = APPLICATION_NAME
		credentials = tools.run_flow(flow, store, flags)
	return credentials
	