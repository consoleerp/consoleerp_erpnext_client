import frappe, os
from frappe.utils import get_url

@frappe.whitelist()
def take_backup():
	backup_dict = backup()
	
	db_url = get_url(os.path.join('backups', os.path.basename(backup_dict.get('db'))))
	files_url = get_url(os.path.join('backups', os.path.basename(backup_dict.get('files'))))
	private_files_url = get_url(os.path.join('backups', os.path.basename(backup_dict.get('private_files'))))
	
	# backupname
	split_name = os.path.basename(backup_dict.get('db')).split('_')
	backup_name = '_'.join(split_name[:-1])
	
	odb = backup_dict.get('odb')
	abs_paths = [odb.backup_path_db, odb.backup_path_files, odb.backup_path_private_files]
	
	return {'db': db_url, 'files': files_url, 'private_files': private_files_url, 'backup_name': backup_name, 'abs_paths': abs_paths}

@frappe.whitelist()
def zip_and_download_files(filename, files):
	
	# string to list
	import ast
	files = ast.literal_eval(files)
	
	zip_path = os.path.join(frappe.get_site_path("private", "backups"), filename + ".consolebackup")
	# this zip can be opened using tar only. not in windows
	# files are having paths relative from sites folder
	cmd_string = """tar -cf %s %s""" % (zip_path, " ".join(files))		
	err, out = frappe.utils.execute_in_shell(cmd_string)
	
	return get_url(os.path.join('backups', os.path.basename(zip_path)))
	
def backup():
	# backup data
	from frappe.utils.backups import BackupGenerator
	odb = BackupGenerator(frappe.conf.db_name, frappe.conf.db_name,\
						  frappe.conf.db_password, db_host = frappe.db.host)
	# older than is not applicable since its forced
	odb.get_backup(older_than=1, ignore_files=False, force=True)
	
	# odb.backup_path_db
	# odb.backup_path_files
	# odb.backup_path_private_files
	return {'db': odb.backup_path_db, 'files': odb.backup_path_files, 'private_files': odb.backup_path_private_files, 'odb': odb}

	
