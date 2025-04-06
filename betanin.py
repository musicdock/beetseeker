#!/usr/bin/env python3

import logging
import os
import json
import sys
import requests
import traceback
import urllib.parse
import config
from slskd import all_downloads_completed, get_download_status

try:
    DEBUG = config.DEBUG
except AttributeError:
    DEBUG = False

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("betanin")


def import_downloads(parent_directory):
    """
    Imports the downloads using the betanin API.
    """
    logger.info(f"Importing downloads from : {parent_directory}")

    if not config.BETANIN_API_KEY:
        logger.error("❌ BETANIN_API_KEY is not configured. Cannot import.")
        return False

    url = f"{config.BETANIN_URL}/api/torrents/"
    headers = {"X-API-Key": config.BETANIN_API_KEY, "Content-Type": "application/x-www-form-urlencoded"}

    # Normalize directory name (remove backslashes and problematic characters)
    directory_name = os.path.basename(parent_directory.replace('\\', '/'))

    # Build the betanin path and encode it correctly for POST
    betanin_path = f"{config.BETANIN_IMPORT_DIRECTORY}/{directory_name}"
    logger.info(f"📁 Import path: {betanin_path}")

    # Check download status
    download_data = get_download_status()
    all_completed, completed_files, total_files = all_downloads_completed(download_data)

    logger.info(f"📊 Global download status: {completed_files}/{total_files} completed files")

    # Check specific directory status
    try:
        from slskd import is_directory_completed
        dir_completed = is_directory_completed(download_data, directory_name)
        logger.info(f"📊 Directory {directory_name} status: {'✅ Completed' if dir_completed else '⏳ Incomplete'}")

        if not dir_completed:
            logger.warning(f"⚠️ Directory not fully completed, but trying to import anyway")
    except Exception as e:
        logger.error(f"❌ Error checking specific directory status: {e}")

    # Prepare data to send
    data = {"both": betanin_path}

    try:
        # Show more details about the request for debugging
        logger.info(f"🔗 BETANIN URL: {url}")
        logger.info(f"🔑 Headers: {headers}")
        logger.info(f"📦 Data: {data}")

        # Try a GET request first to verify connectivity
        logger.info("🔍 Checking betanin connection...")
        check_url = f"{config.BETANIN_URL}/api/torrents/?page=1&per_page=1"
        logger.info(f"🔗 TEST URL: {check_url}")

        try:
            check_headers = {"X-API-Key": config.BETANIN_API_KEY, "accept": "application/json"}
            check_response = requests.get(check_url, headers=check_headers, timeout=10)
            logger.info(f"📡 Verification response: Status {check_response.status_code}")

            if check_response.status_code == 200:
                logger.info("✅ Betanin connection established correctly")
                try:
                    logger.debug(f"📊 Data: {json.dumps(check_response.json(), indent=2)}")
                except:
                    logger.debug(f"📝 Response: {check_response.text[:500]}")
            else:
                logger.error(f"❌ Error connecting to betanin: {check_response.status_code}")
                if check_response.status_code == 401:
                    logger.error("🔐 Authentication error: Incorrect API key or missing permissions")
                logger.error(f"📝 Full response: {check_response.text[:500]}")
                return False
        except Exception as e:
            logger.error(f"❌ Error checking connection: {e}")
            logger.error(traceback.format_exc())
            return False

        # Now perform the import request
        logger.info(f"📤 Sending import request to betanin...")

        try:
            # Ensure the data is sent correctly
            # Use urllib.parse to encode the parameters correctly
            encoded_data = urllib.parse.urlencode(data)
            logger.debug(f"📦 Encoded data: {encoded_data}")

            # Ensure Content-Type is correct for form data
            import_headers = {
                "X-API-Key": config.BETANIN_API_KEY,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }

            # Realizar la solicitud con datos codificados
            response = requests.post(url, headers=import_headers, data=encoded_data, timeout=30)

            logger.info(f"📡 betanin response: Status {response.status_code}")
            logger.debug(f"📝 Full response: {response.text[:500]}")

            if response.status_code == 200:
                logger.info(f"✅ Import successful in betanin")
                return True
            else:
                logger.error(f"❌ Error in import. Code: {response.status_code}")
                try:
                    logger.error(f"📝 JSON response: {json.dumps(response.json(), indent=2)}")
                except:
                    logger.error(f"📝 Text response: {response.text[:500]}")

                # Sugerencias específicas según el código de error
                if response.status_code == 400:
                    logger.error("❌ Error 400: Incorrect request. Check data format.")
                elif response.status_code == 404:
                    logger.error("❌ Error 404: Route not found. Check API URL.")
                elif response.status_code == 422:
                    logger.error("❌ Error 422: Invalid data. Check directory path.")

                return False
        except Exception as e:
            logger.error(f"❌ Error in POST request: {e}")
            logger.error(traceback.format_exc())
            return False

    except Exception as e:
        logger.error(f"❌ Unexpected error communicating with betanin: {e}")
        logger.error(traceback.format_exc())
        return False


def get_download_outcome(download_id):
    """
    Gets the outcome of the download from the betanin API.
    """
    logger.info(f"🔍 Getting download outcome for ID {download_id}...")

    url = f"{config.BETANIN_URL}/api/torrents/{download_id}/console/stdout"
    headers = {"X-API-Key": config.BETANIN_API_KEY, "accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        logger.info(f"✅ Result obtained correctly")

        for item in data:
            logger.info(f"📜 Output: {item.get('data', '')}")

        return data
    except Exception as e:
        logger.error(f"❌ Error getting download outcome: {e}")
        logger.error(traceback.format_exc())
        return None


def check_manual_intervention_needed():
    """
    Checks if manual intervention in betanin is needed.
    """
    logger.info("🔍 Checking if manual intervention is needed...")

    # Verificar si tenemos API key
    if not config.BETANIN_API_KEY:
        logger.error("❌ Cannot verify: BETANIN_API_KEY is not configured")
        return False

    url = f"{config.BETANIN_URL}/api/torrents/"
    headers = {"X-API-Key": config.BETANIN_API_KEY, "accept": "application/json"}
    params = {"page": 1, "per_page": 1}

    try:
        logger.info(f"🔗 URL: {url}")
        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code != 200:
            logger.error(f"❌ Error checking status. Code: {response.status_code}")
            return False

        data = response.json()

        if not data.get('torrents') or len(data['torrents']) == 0:
            logger.warning("⚠️ No torrents found in betanin")
            return False

        download_id = data['torrents'][0]['id']
        download_status = data['torrents'][0]['status']
        download_name = data['torrents'][0]['name']

        logger.info(f"📊 Last torrent status: {download_status}, name: {download_name}")

        if download_status != "COMPLETED":
            logger.warning(f"⚠️ Manual intervention required in betanin. Status: {download_status}")
            logger.warning(f"⚠️ Please check {config.BETANIN_URL}")
            get_download_outcome(download_id)
            return True

        logger.info("✅ No manual intervention required")
        return False
    except Exception as e:
        logger.error(f"❌ Error checking if manual intervention is needed: {e}")
        logger.error(traceback.format_exc())
        return False  # In case of error, assume no manual intervention is needed