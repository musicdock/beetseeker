#!/usr/bin/env python3

import requests
import logging
import sys
import json
import traceback
import config

# Configurar logging con nivel basado en config.DEBUG
try:
    DEBUG = config.DEBUG
except AttributeError:
    # Si no está definido en config, default a False
    DEBUG = False

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("slskd")


def get_subdirectories(directory):
    """
    Returns a set of subdirectories obtained from the download status API.
    Uses the API instead of direct filesystem access.
    """
    logger.info(f"🔍 Getting directories from slskd API...")

    download_data = get_download_status()
    directories = set()

    if not download_data:
        logger.warning("⚠️ Could not get data from slskd API")
        return directories

    logger.debug(f"📊 Download data received: {len(download_data)} users")

    for user in download_data:
        for directory_info in user.get('directories', []):
            # Extraer el nombre del directorio de la ruta completa
            dir_path = directory_info.get('directory', '')
            if dir_path:
                # Normalizar la ruta (convertir barras invertidas a barras normales)
                dir_path = dir_path.replace('\\', '/')
                # Obtener el último componente de la ruta como nombre del directorio
                dir_name = dir_path.rstrip('/').split('/')[-1]
                directories.add(dir_name)
                if DEBUG:
                    logger.debug(f"📁 Directory found: {dir_name} (full path: {dir_path})")

    if directories:
        logger.info(f"✅ {len(directories)} directories found")
        if DEBUG:
            logger.debug(
                f"📂 List of directories: {', '.join(list(directories)[:5])}{'...' if len(directories) > 5 else ''}")
    else:
        logger.info("📭 No directories found")

    return directories


def get_download_status():
    """
    Returns the download status from the slskd API.
    """
    url = f"{config.SLSKD_URL}/api/v0/transfers/downloads"
    params = {'includeRemoved': 'false'}
    headers = {'X-API-Key': config.SLSKD_API_KEY}

    try:
        logger.info(f"🔄 Consulting slskd API: {url}")
        if DEBUG:
            logger.debug(f"🔑 Headers: {headers}")
            logger.debug(f"🔍 Parameters: {params}")

        response = requests.get(url, params=params, headers=headers, timeout=10)

        logger.info(f"📡 slskd response: Status {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Download data received correctly")
            if DEBUG:
                sample_data = data[:1] if data else []
                logger.debug(f"📊 Sample data: {json.dumps(sample_data, indent=2)}")
            return data
        else:
            logger.error(f"❌ Error getting data. Code: {response.status_code}")
            logger.error(f"📝 Response: {response.text[:500]}")
            return []
    except Exception as e:
        logger.error(f"❌ Error getting download status: {e}")
        if DEBUG:
            logger.error(traceback.format_exc())
        return []


def all_downloads_completed(data):
    """
    Checks if all downloads are completed.
    """
    if not data:
        logger.warning("⚠️ No download data to check")
        return False, 0, 0

    total_files = 0
    completed_files = 0

    logger.info("🔍 Checking download status...")

    for user in data:
        username = user.get('username', 'Unknown')
        for directory in user.get('directories', []):
            dir_name = directory.get('directory', '').replace('\\', '/').split('/')[-1]

            for file in directory.get('files', []):
                filename = file.get('filename', 'Unknown')
                state = file.get('state', 'Unknown')

                total_files += 1

                if state == 'Completed, Succeeded':
                    completed_files += 1
                    if DEBUG:
                        logger.debug(f"✅ File completed: {filename} in {dir_name} of {username}")
                else:
                    if DEBUG:
                        logger.debug(f"⏳ File in progress: {filename} in {dir_name} of {username}, state: {state}")

    all_completed = (completed_files == total_files and total_files > 0)

    if all_completed:
        logger.info(f"✅ All downloads completed: {completed_files}/{total_files} files")
    else:
        logger.info(f"⏳ Downloads in progress: {completed_files}/{total_files} files completed")

    return all_completed, completed_files, total_files


def get_completed_directories(data):
    """
    Returns a list of directories that have all their downloads completed.

    Args:
        data: Download status data from the API

    Returns:
        List of directories with all downloads completed
    """
    if not data:
        logger.warning("⚠️ No download data to check complete directories")
        return []

    logger.info("🔍 Analyzing directories with completed downloads...")

    # Dictionary to store directory information: {dir_name: [total_files, completed_files]}
    directories_status = {}

    # Process data to calculate total and completed files per directory
    for user in data:
        for directory in user.get('directories', []):
            # Get normalized directory name
            dir_path = directory.get('directory', '')
            if not dir_path:
                continue

            # Normalize directory name
            dir_path = dir_path.replace('\\', '/')
            dir_name = dir_path.rstrip('/').split('/')[-1]

            # Initialize counters if it's the first time we see this directory
            if dir_name not in directories_status:
                directories_status[dir_name] = [0, 0]  # [total_files, completed_files]

            # Count files in this directory
            for file in directory.get('files', []):
                directories_status[dir_name][0] += 1  # Increment total_files

                if file.get('state') == 'Completed, Succeeded':
                    directories_status[dir_name][1] += 1  # Increment completed_files

    # Determine which directories are complete
    completed_directories = []
    in_progress_directories = []

    for dir_name, counts in directories_status.items():
        total_files, completed_files = counts

        if total_files > 0 and completed_files == total_files:
            completed_directories.append(dir_name)
            if DEBUG:
                logger.debug(f"✅ Directory complete: {dir_name} ({completed_files}/{total_files} files)")
        else:
            in_progress_directories.append(dir_name)
            if DEBUG:
                logger.debug(f"⏳ Directory in progress: {dir_name} ({completed_files}/{total_files} files)")

    logger.info(f"✅ {len(completed_directories)} directories with completed downloads")
    logger.info(f"⏳ {len(in_progress_directories)} directories with downloads in progress")

    if DEBUG and completed_directories:
        preview = completed_directories[:5]
        logger.debug(f"📂 Sample of complete directories: {preview}{'...' if len(completed_directories) > 5 else ''}")

    return completed_directories


def is_directory_completed(data, directory_name):
    """
    Checks if a specific directory has all its downloads completed.

    Args:
        data: Download status data from the API
        directory_name: Name of the directory to check

    Returns:
        bool: True if all downloads for this directory are completed, False otherwise
    """
    if not data:
        logger.warning(f"⚠️ No data to check status of {directory_name}")
        return False

    total_files = 0
    completed_files = 0

    # Normalize directory name for comparisons
    directory_name_lower = directory_name.lower()

    for user in data:
        for directory in user.get('directories', []):
            dir_path = directory.get('directory', '')
            if not dir_path:
                continue

            # Normalize and extract directory name
            dir_path = dir_path.replace('\\', '/')
            dir_name = dir_path.rstrip('/').split('/')[-1]

            # Check if this is the directory we are looking for (case insensitive comparison)
            if dir_name.lower() == directory_name_lower:
                # Count files and their state
                for file in directory.get('files', []):
                    total_files += 1
                    if file.get('state') == 'Completed, Succeeded':
                        completed_files += 1

    # If we don't find any files, we can't determine the status
    if total_files == 0:
        logger.warning(f"⚠️ No files found for directory {directory_name}")
        return False

    # Directory is complete if all files are completed
    is_completed = (completed_files == total_files)

    if is_completed:
        logger.info(f"✅ Directory {directory_name} complete: {completed_files}/{total_files} files")
    else:
        logger.info(f"⏳ Directory {directory_name} in progress: {completed_files}/{total_files} files")

    return is_completed