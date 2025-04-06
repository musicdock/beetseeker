#!/usr/bin/env python3

import time
import logging
import sys
import json
import traceback
from collections import deque
import config
import slskd
import betanin

try:
    DEBUG = config.DEBUG
except AttributeError:
    DEBUG = False

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("main")

# Banner inicial para distinguir reinicios
logger.info("🚀 Starting BeetSeeker with smart queueing 🚀")
logger.info("=" * 80)

# Verificar configuración
logger.info(f"📋 Configuration:")
logger.info(f"- SLSKD_URL: {config.SLSKD_URL}")
logger.info(f"- BETANIN_URL: {config.BETANIN_URL}")
logger.info(f"- DOWNLOADS_DIRECTORY: {config.DOWNLOADS_DIRECTORY}")
logger.info(f"- BETANIN_IMPORT_DIRECTORY: {config.BETANIN_IMPORT_DIRECTORY}")
logger.info(f"- SLSKD API key configured: {'✅ Yes' if config.SLSKD_API_KEY else '❌ No'}")
logger.info(f"- BETANIN API key configured: {'✅ Yes' if config.BETANIN_API_KEY else '❌ No'}")
logger.info(f"- DEBUG mode: {'✅ Enabled' if DEBUG else '❌ Disabled'}")

if not config.BETANIN_API_KEY:
    logger.error(
        "⚠️ BETANIN_API_KEY is not configured in config.py. You need to configure it to enable integration with betanin.")
    logger.error("⚠️ Please access the betanin web interface, generate an API key and add it to config.py")

# Processing queue
subdirectory_queue = deque()

# Tracking sets
previous_subdirectories = set()
processed_directories = set()    
processing_failures = {}  # Directory -> number of failed attempts

# Check initial download status
logger.info("🔍 Checking initial download status...")
download_data = slskd.get_download_status()

# Get directories and check which are completed
logger.info("🔍 Getting initial directories...")
all_subdirectories = slskd.get_subdirectories(config.DOWNLOADS_DIRECTORY)
completed_directories = slskd.get_completed_directories(download_data)

# Update previous directories set
previous_subdirectories = all_subdirectories

# Encolar directorios completos iniciales
for directory in completed_directories:
    if directory not in processed_directories:
        logger.info(f"📥 Enqueueing complete directory: {directory}")
        subdirectory_queue.append(directory)

if subdirectory_queue:
    logger.info(f"📋 Initial queue: {len(subdirectory_queue)} complete directories ready to process")
else:
    logger.info("📋 Initial queue is empty, no complete directories to process")


# Function to show queue status
def log_queue_status():
    if subdirectory_queue:
        logger.info(f"📋 Current queue: {len(subdirectory_queue)} directories")
        if DEBUG and len(subdirectory_queue) > 0:
            preview = list(subdirectory_queue)[:3]
            logger.debug(f"First in queue: {preview}{'...' if len(subdirectory_queue) > 3 else ''}")
    else:
        logger.info("📋 Queue is empty, no directories to process")


# Bucle principal
iteration = 0
while True:
    try:
        iteration += 1
        logger.info(f"\n--- ITERATION {iteration} ---")

        # Obtener directorios actuales y estado de descargas
        logger.info("🔍 Checking directories and download status...")
        download_data = slskd.get_download_status()
        current_subdirectories = slskd.get_subdirectories(config.DOWNLOADS_DIRECTORY)
        completed_directories = slskd.get_completed_directories(download_data)

        # Encontrar nuevos directorios
        new_subdirectories = current_subdirectories - previous_subdirectories

        # Actualizar la cola con nuevos directorios completos
        if new_subdirectories:
            logger.info(f"✨ {len(new_subdirectories)} new directories detected")

            for directory in new_subdirectories:
                if directory in completed_directories and directory not in processed_directories:
                    logger.info(f"📥 Enqueueing new complete directory: {directory}")
                    subdirectory_queue.append(directory)

        # También verificar directorios existentes que se han completado recientemente
        for directory in current_subdirectories:
            if (directory in completed_directories and
                    directory not in processed_directories and
                    directory not in subdirectory_queue):
                logger.info(f"📥 Enqueueing recently completed directory: {directory}")
                subdirectory_queue.append(directory)

        # Check queue status
        log_queue_status()

        # Process directories in queue
        if subdirectory_queue:
            # Get next directory without removing it from the queue yet
            subdirectory = subdirectory_queue[0]

            # Verificar nuevamente que el directorio está completo (por si cambió mientras estaba en cola)
            is_completed = slskd.is_directory_completed(download_data, subdirectory)

            if is_completed:
                logger.info(f"🔄 PROCESSING complete directory: {subdirectory}")

                # Verificar configuración de betanin antes de intentar importar
                if not config.BETANIN_API_KEY:
                    logger.error("❌ Cannot import to betanin: BETANIN_API_KEY is not configured")
                    logger.error("❌ Configure it in config.py and restart BeetSeeker")
                    # Remove directory from queue to avoid blocking
                    subdirectory_queue.popleft()
                    continue

                # Intentar importar
                success = betanin.import_downloads(subdirectory)

                if success:
                    logger.info(f"✅ Directory sent to betanin: {subdirectory}")

                    logger.info("🔍 Checking if manual intervention is needed...")
                    if betanin.check_manual_intervention_needed():
                        logger.warning(f"⚠️ Manual intervention required for {subdirectory}")
                    else:
                        logger.info(f"✅ Successful processing of {subdirectory}")

                    # Marcar como procesado y quitar de la cola
                    processed_directories.add(subdirectory)
                    subdirectory_queue.popleft()
                else:
                    # Registrar el fallo
                    if subdirectory in processing_failures:
                        processing_failures[subdirectory] += 1
                    else:
                        processing_failures[subdirectory] = 1

                    # Si ha fallado demasiadas veces, quitarlo de la cola
                    if processing_failures[subdirectory] >= 3:
                        logger.error(f"❌ Too many failed attempts for {subdirectory}, skipping")
                        subdirectory_queue.popleft()
                    else:
                        logger.error(
                            f"❌ Import failed for {subdirectory} (attempt {processing_failures[subdirectory]}/3)")
                        # Move to end of queue to try later
                        subdirectory_queue.popleft()
                        subdirectory_queue.append(subdirectory)
            else:
                logger.info(f"⏸️ The directory {subdirectory} is not complete, moving to end of queue")
                # Move to end of queue to check later
                subdirectory_queue.popleft()
                subdirectory_queue.append(subdirectory)
        else:
            logger.info("⏸️ No complete directories to process")

        # Update previous directories
        previous_subdirectories = current_subdirectories

    except Exception as e:
        logger.error(f"❌ Error in main loop: {e}")
        logger.error(traceback.format_exc())

    # Esperar antes de la próxima verificación
    logger.info(f"💤 Waiting 5 seconds before next check...\n")
    time.sleep(5)