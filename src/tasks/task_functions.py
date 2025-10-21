"""
Predefined task functions that can be scheduled
Each function should receive parameters as kwargs
"""

import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import pandas as pd

logger = logging.getLogger(__name__)


def send_email_task(**kwargs) -> Dict[str, Any]:
    try:
        recipient_email = kwargs.get('recipient_email')
        subject = kwargs.get('subject')
        message = kwargs.get('message')
        sender_email = kwargs.get('sender_email', settings.DEFAULT_FROM_EMAIL)
        
        if not all([recipient_email, subject, message]):
            raise ValueError("recipient_email, subject and message parameters are required")
        
        send_mail(
            subject=subject,
            message=message,
            from_email=sender_email,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        
        logger.info(f"Email sent successfully to {recipient_email}")
        
        return {
            'status': 'success',
            'message': f'Email sent successfully to {recipient_email}',
            'timestamp': timezone.now().isoformat(),
            'recipient': recipient_email,
            'subject': subject
        }
        
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error sending email: {str(e)}',
            'timestamp': timezone.now().isoformat()
        }


def process_excel_task(**kwargs) -> Dict[str, Any]:
    try:

        input_file_path = kwargs.get('input_file_path')
        output_file_path = kwargs.get('output_file_path')
        tax_rate = float(kwargs.get('tax_rate', 0.1))
        
        if not all([input_file_path, output_file_path]):
            raise ValueError("input_file_path and output_file_path parameters are required")
        
        df = pd.read_excel(input_file_path)
        
        required_columns = ['Customer Name', 'Product Name', 'Price', 'Purchase Date']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"Missing columns in Excel file: {missing_columns}")
        
        df['Tax'] = df['Price'] * tax_rate
        df['Total with Tax'] = df['Price'] + df['Tax']
        df.to_excel(output_file_path, index=False)
        
        stats = {
            'total_records': len(df),
            'total_amount': df['Price'].sum(),
            'total_tax': df['Tax'].sum(),
            'total_with_tax': df['Total with Tax'].sum(),
            'tax_rate': tax_rate,
            'unique_customers': df['Customer Name'].nunique(),
            'unique_products': df['Product Name'].nunique(),
        }
        
        logger.info(f"Excel file processed successfully: {len(df)} records")
        
        return {
            'status': 'success',
            'message': f'Excel file processed successfully',
            'timestamp': timezone.now().isoformat(),
            'input_file': input_file_path,
            'output_file': output_file_path,
            'statistics': stats
        }
        
    except Exception as e:
        logger.error(f"Error processing Excel file: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error processing Excel file: {str(e)}',
            'timestamp': timezone.now().isoformat()
        }


def cleanup_temp_folder_task(**kwargs) -> Dict[str, Any]:
    try:
        temp_path = kwargs.get('temp_path', '/tmp')
        
        days_old = int(kwargs.get('days_old', 7))
        file_extensions = kwargs.get('file_extensions', [])
        dry_run = kwargs.get('dry_run', False)
        
        if not os.path.exists(temp_path):
            raise ValueError(f"Temp directory {temp_path} does not exist")
        
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        deleted_files = []
        deleted_dirs = []
        total_size_freed = 0
        
        for root, dirs, files in os.walk(temp_path, topdown=False):
            for file in files:
                file_path = os.path.join(root, file)
                
                if file_extensions:
                    file_ext = os.path.splitext(file)[1].lower()
                    if file_ext not in file_extensions:
                        continue
                
                try:
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    file_size = os.path.getsize(file_path)
                    
                    if file_mtime < cutoff_date:
                        if not dry_run:
                            os.remove(file_path)
                        
                        deleted_files.append({
                            'path': file_path,
                            'size': file_size,
                            'modified_date': file_mtime.isoformat(),
                            'deleted': not dry_run
                        })
                        total_size_freed += file_size
                        
                except Exception as e:
                    logger.warning(f"Could not process file {file_path}: {str(e)}")
            
            if not dry_run:
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if not os.listdir(dir_path):
                            os.rmdir(dir_path)
                            deleted_dirs.append({
                                'path': dir_path,
                                'deleted': True
                            })
                    except Exception as e:
                        logger.warning(f"Could not remove directory {dir_path}: {str(e)}")
        
        action_text = "would be deleted" if dry_run else "deleted"
        logger.info(f"Temp cleanup completed: {len(deleted_files)} files {action_text}")
        
        return {
            'status': 'success',
            'message': f'Temp folder cleanup completed successfully',
            'timestamp': timezone.now().isoformat(),
            'temp_directory': temp_path,
            'days_old': days_old,
            'dry_run': dry_run,
            'deleted_files_count': len(deleted_files),
            'deleted_dirs_count': len(deleted_dirs),
            'total_size_freed_bytes': total_size_freed,
            'deleted_files': deleted_files[:10],
            'deleted_dirs': deleted_dirs[:5] 
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up temp folder: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error cleaning up temp folder: {str(e)}',
            'timestamp': timezone.now().isoformat()
        }


def backup_database_task(**kwargs) -> Dict[str, Any]:
    try:
        backup_path = kwargs.get('backup_path')
        backup_name = kwargs.get('backup_name', f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        compress = kwargs.get('compress', True)
        
        if not backup_path:
            raise ValueError("backup_path parameter is required")
        
        os.makedirs(backup_path, exist_ok=True)
        
        backup_filename = f"{backup_name}.sql"
        if compress:
            backup_filename += ".gz"
        
        full_backup_path = os.path.join(backup_path, backup_filename)
        
        db_settings = settings.DATABASES['default']
        pg_dump_cmd = [
            'pg_dump',
            '-h', db_settings['HOST'],
            '-p', str(db_settings['PORT']),
            '-U', db_settings['USER'],
            '-d', db_settings['NAME'],
        ]
        
        if compress:
            pg_dump_cmd.extend(['-Z', '9'])  
        
        import subprocess
        
        with open(full_backup_path, 'w') as backup_file:
            result = subprocess.run(
                pg_dump_cmd,
                stdout=backup_file,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, 'PGPASSWORD': db_settings['PASSWORD']}
            )
        
        if result.returncode != 0:
            raise Exception(f"Error running pg_dump: {result.stderr}")
        
        backup_size = os.path.getsize(full_backup_path)
        
        logger.info(f"Database backup created successfully: {full_backup_path}")
        
        return {
            'status': 'success',
            'message': f'Database backup created successfully',
            'timestamp': timezone.now().isoformat(),
            'backup_path': full_backup_path,
            'backup_size_bytes': backup_size,
            'compressed': compress,
            'database_name': db_settings['NAME']
        }
        
    except Exception as e:
        logger.error(f"Error creating database backup: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error creating database backup: {str(e)}',
            'timestamp': timezone.now().isoformat()
        }


AVAILABLE_TASK_FUNCTIONS = {
    'send_email_task': {
        'function': send_email_task,
        'description': 'Send email to specified address',
        'parameters': [
            {'name': 'recipient_email', 'type': 'email', 'required': True, 'description': 'Recipient email address'},
            {'name': 'subject', 'type': 'string', 'required': True, 'description': 'Email subject'},
            {'name': 'message', 'type': 'string', 'required': True, 'description': 'Email message'},
            {'name': 'sender_email', 'type': 'email', 'required': False, 'description': 'Sender email address'},
        ]
    },
    'process_excel_task': {
        'function': process_excel_task,
        'description': 'Process Excel file and calculate tax',
        'parameters': [
            {'name': 'input_file_path', 'type': 'string', 'required': True, 'description': 'Input Excel file path'},
            {'name': 'output_file_path', 'type': 'string', 'required': True, 'description': 'Output Excel file path'},
            {'name': 'tax_rate', 'type': 'float', 'required': False, 'description': 'Tax rate (default: 0.1)'},
        ]
    },
    'cleanup_temp_folder_task': {
        'function': cleanup_temp_folder_task,
        'description': 'Cleanup old files from temp folder',
        'parameters': [
            {'name': 'temp_path', 'type': 'string', 'required': False, 'description': 'Temp directory path (default: /tmp)'},
            {'name': 'days_old', 'type': 'integer', 'required': False, 'description': 'Number of days for file age (default: 7)'},
            {'name': 'file_extensions', 'type': 'json', 'required': False, 'description': 'List of file extensions to filter'},
            {'name': 'dry_run', 'type': 'boolean', 'required': False, 'description': 'If true, only report what would be deleted'},
        ]
    },
    'backup_database_task': {
        'function': backup_database_task,
        'description': 'Create backup of PostgreSQL database',
        'parameters': [
            {'name': 'backup_path', 'type': 'string', 'required': True, 'description': 'Backup storage path'},
            {'name': 'backup_name', 'type': 'string', 'required': False, 'description': 'Backup file name'},
            {'name': 'compress', 'type': 'boolean', 'required': False, 'description': 'Compress backup'},
        ]
    },
}
