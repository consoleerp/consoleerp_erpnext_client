import frappe
import httplib2
import os, io

from apiclient import discovery
from apiclient.http import MediaFileUpload
from apiclient.http import MediaIoBaseDownload
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

from frappe.utils import update_progress_bar

SCOPES = 'https://www.googleapis.com/auth/drive.file'
CLIENT_SECRET_FILE = '/home/consoleadmin/consoleerp/google_drive/client_secret.json'
APPLICATION_NAME = 'Console ERP Data Backup'

def upload_backup():

	credentials = get_credentials()
	http = credentials.authorize(httplib2.Http())
	drive_service = discovery.build('drive', 'v3', http=http)

	client_folder_id = get_client_folder_id(drive_service)
	print("Client Folder ID: %s" % client_folder_id)

	# backup data
	from consoleerp_erpnext_client.utils.system import backup
	backup_dict = backup()
	print("Backup Successful : %s" % os.path.abspath(backup_dict['db']))

	today_folder_id = get_today_folder_id(drive_service, client_folder_id)

	for filepath in [os.path.abspath(backup_dict['db']), os.path.abspath(backup_dict['private_files']), os.path.abspath(backup_dict['files'])]:
		filename = os.path.basename(filepath)
		response = drive_service.files().create(body={'name': filename, 'parents': [today_folder_id]}, fields="id", media_body=MediaFileUpload(filepath)).execute()
		print("Uploaded %s : %s" % (filename, response.get("id")))
	
def get_client_folder_id(drive_service):
	"""
	Returns the client folder to take the backups
	TODO fetch client name
	"""
	client_name = frappe.db.get_value("ConsoleERP Settings", filters="*", fieldname="client_name")	
	if not client_name:
		print("Client Name not set")
		return None
	
	print("Client Name: %s" % client_name)
	
	response = drive_service.files().list(q="name = '%s' and mimeType='application/vnd.google-apps.folder'" % client_name, pageSize=1,
														fields='nextPageToken, files(id, name)').execute()
	for file in response.get("files", []):
		return file.get("id")		
	
	# client folder doesnt exist. creating folder	
	file = drive_service.files().create(body={ 'name': client_name, 'mimeType': 'application/vnd.google-apps.folder'},
																	fields="id").execute()	
	print("Folder Created. ID: %s" % file.get("id"))
	
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

def download_latest_client_backup():
	credentials = get_credentials()
	http = credentials.authorize(httplib2.Http())
	drive_service = discovery.build('drive', 'v3', http=http)
	client_id = get_client_folder_id(drive_service)

	results = drive_service.files().list(q="'{}' in parents".format(client_id),
						pageSize=10, fields="files(id,name)", orderBy="modifiedTime desc").execute()
	recent_folder = results.get("files", []) and results.get("files")[0].get("name")
	if not recent_folder:
		print("No recent backups found")
		return
	print("Recent Backup Found ON : {}".format(recent_folder))
	recent_folder = results.get("files")[0].get("id")

	# Download all files in the recent_folder and proceed
	backup_files = drive_service.files().list(q="'{}' in parents".format(recent_folder),
											fields="files(id,name)").execute()
	if not backup_files:
		print("No files found in the folder")
		return
	sitepath = os.path.join(frappe.get_site_path(), recent_folder)
	os.mkdir(sitepath)
	for file in backup_files["files"]:
		request = drive_service.files().get_media(fileId=file.get("id"))
		fh = io.FileIO(os.path.join(frappe.get_site_path(), recent_folder, file.get("name")), mode='w')
		downloader = MediaIoBaseDownload(fh, request)
		done = False
		while done is False:
			status, done = downloader.next_chunk()
			update_progress_bar("Downloading {} {}%".format(file.get("name", ''), round(status.progress()*100)), status.progress() * 100, 100)
		print('')
	# execute restore methods
	print("bench --force --site {} restore {} --with-public-files {} --with-private-files {}".format(
			os.path.basename(os.path.normpath(frappe.get_site_path())),
			[os.path.join(sitepath, x.get("name")) for x in backup_files["files"] if "database" in x.get("name")][0], 
			[os.path.join(sitepath, x.get("name")) for x in backup_files["files"] if not "database" in x.get("name") and not "private" in x.get("name")][0],
			[os.path.join(sitepath, x.get("name")) for x in backup_files["files"] if "private_files" in x.get("name")][0]))
	print()
	print("rm -rf sites{}".format(sitepath[1:]))
	print()

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
	