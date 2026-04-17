"""
Background scheduler — cleans up expired files every hour.
Runs as an asyncio task started in main.py lifespan.
"""
import asyncio
import logging
import os

logger = logging.getLogger(__name__)


async def cleanup_expired_files() -> None:
    """Delete physical files that have passed their expiry timestamp."""
    from db import get_expired_files, mark_file_deleted

    try:
        expired = await get_expired_files()
        if not expired:
            logger.debug("Cleanup: no expired files found")
            return

        logger.info("Cleanup: %d expired file(s) to delete", len(expired))
        for f in expired:
            filepath = f["filepath"]
            file_id = f["file_id"]
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info("Deleted expired file: %s", filepath)
                else:
                    logger.info("File already gone: %s", filepath)
                await mark_file_deleted(file_id)
            except Exception as exc:
                logger.error("Error deleting %s: %s", filepath, exc)

    except Exception as exc:
        logger.error("Cleanup job crashed: %s", exc)


async def run_scheduler() -> None:
    """Loop: wait 1 hour, run cleanup, repeat."""
    while True:
        await asyncio.sleep(3600)
        logger.info("Running hourly cleanup...")
        await cleanup_expired_files()
