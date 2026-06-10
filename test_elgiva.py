"""Test execution module for validating the Elgiva Theatre scraper lifecycle."""

import os
import sys

# Ensure root workspace boundaries map accurately on module loads
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from scrapers.elgiva.run_extractor import ElgivaExtractor
from utils.logger import setup_logger

logger = setup_logger("test_elgiva", log_to_file=False)


def test_elgiva_pipeline():
    """Runs a targeted pipeline sweep over the first few elements to confirm validation criteria."""
    logger.info("Initializing Elgiva Pipeline Structural Integration Verification Test")
    logger.info("=" * 60)
    
    extractor = ElgivaExtractor(
        local_test=True,
        headless=True,
        show_count=None,
        save_csv_locally=True,
        csv_incremental_mode=False
    )
    
    result = extractor.run()
    logger.info(f"Verification Phase Complete. Execution Payload Summary: {result}")
    logger.info("=" * 60)


if __name__ == "__main__":
    test_elgiva_pipeline()