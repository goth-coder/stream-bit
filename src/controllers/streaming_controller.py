"""
Streaming Controller for Bitcoin Price Pipeline.

This controller orchestrates the complete Bitcoin streaming pipeline,
using the separated extractor and loader modules.
"""

import time
import logging
from typing import Optional
from src.services.extractors.bitcoin_extractor import BitcoinExtractor
from src.services.loaders.firehose_loader import FirehoseLoader

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class StreamingController:
    """
    Controls the Bitcoin streaming pipeline.

    Responsibilities:
    - Orchestrate extraction and loading
    - Handle timing and retry logic
    - Provide monitoring and logging
    - Manage error conditions
    """

    def __init__(
        self,
        firehose_stream_name: str,
        extraction_interval: int = 8,  # Ajustado para 8s (base do range 8-11s)
        max_retries: int = 3,
    ):
        """
        Initialize streaming controller.

        Args:
            firehose_stream_name: Name of the Firehose stream
            extraction_interval: Base interval between extractions (seconds)
            max_retries: Maximum retry attempts for failed operations
        """
        self.firehose_stream_name = firehose_stream_name
        self.extraction_interval = extraction_interval
        self.max_retries = max_retries

        # Initialize components
        self.extractor = BitcoinExtractor()
        self.loader = FirehoseLoader(stream_name=firehose_stream_name)

        # Statistics
        self.total_extractions = 0
        self.successful_extractions = 0
        self.total_uploads = 0
        self.successful_uploads = 0

        logger.info(
            f"Streaming controller initialized for stream: {firehose_stream_name}"
        )

    def run_single_cycle(self) -> bool:
        """
        Run a single extraction-upload cycle.

        Returns:
            True if successful, False if failed
        """
        cycle_start = time.time()
        self.total_extractions += 1

        try:
            # Extract Bitcoin price
            logger.info("🔍 Extracting Bitcoin price...")
            data = self.extractor.extract_with_retry(max_retries=self.max_retries)

            if data is None:
                logger.error("❌ Extraction failed after retries")
                return False

            self.successful_extractions += 1
            logger.info(f"✅ Extracted: R$ {data['price_brl']:,.2f}")

            # Upload to Firehose
            logger.info("📤 Uploading to Firehose...")
            self.total_uploads += 1

            upload_result = self.loader.send_record(data)

            # Log detailed upload result for debugging
            logger.debug(f"🔍 Upload result details: {upload_result}")

            if upload_result.get("status") == "success":
                self.successful_uploads += 1
                record_id = upload_result.get("record_id", "Unknown")
                http_status = upload_result.get("http_status", "Unknown")
                data_size = upload_result.get("data_size_bytes", 0)
                cycle_time = time.time() - cycle_start

                logger.info(f"✅ Upload successful - RecordId: {record_id}")
                logger.info(f"📊 HTTP Status: {http_status}, Size: {data_size} bytes")
                logger.info(f"⏱️ Cycle completed in {cycle_time:.2f}s")
                return True
            else:
                # Detailed error logging
                status = upload_result.get("status", "unknown")
                error_msg = upload_result.get("error", "No error message provided")
                http_status = upload_result.get("http_status", "unknown")
                timestamp = upload_result.get("timestamp", "unknown")

                logger.error(f"❌ Upload failed with status: {status}")
                logger.error(f"🔍 Error details: {error_msg}")
                logger.error(f"📊 HTTP Status: {http_status}")
                logger.error(f"⏰ Error timestamp: {timestamp}")

                # Log the full response for debugging
                logger.debug(f"🔍 Full upload response: {upload_result}")
                return False

        except Exception as e:
            logger.error(f"❌ Cycle failed with exception: {e}")
            return False

    def run_continuous_streaming(
        self, duration_hours: Optional[float] = None, verbose: bool = True
    ) -> None:
        """
        Run continuous Bitcoin streaming.

        Args:
            duration_hours: Max duration in hours (None for infinite)
            verbose: Whether to print verbose statistics
        """
        logger.info("🚀 Starting continuous Bitcoin streaming...")

        start_time = time.time()
        cycles_completed = 0

        try:
            while True:
                # Check duration limit
                if duration_hours is not None:
                    elapsed_hours = (time.time() - start_time) / 3600
                    if elapsed_hours >= duration_hours:
                        logger.info(f"⏰ Duration limit reached: {duration_hours}h")
                        break

                # Run extraction-upload cycle
                success = self.run_single_cycle()
                cycles_completed += 1

                # Print statistics periodically
                if verbose and cycles_completed % 10 == 0:
                    self.print_statistics()

                # Calculate sleep time
                sleep_time = self.extractor.get_recommended_sleep_time(
                    success=success, base_interval=self.extraction_interval
                )

                logger.info(f"💤 Sleeping for {sleep_time}s...")
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("\n🛑 Streaming stopped by user")
        except Exception as e:
            logger.error(f"💥 Streaming stopped due to error: {e}")
        finally:
            # Final statistics
            elapsed_time = time.time() - start_time
            logger.info("\n📊 Final Statistics:")
            logger.info(f"   Duration: {elapsed_time / 3600:.2f}h")
            logger.info(f"   Cycles: {cycles_completed}")
            self.print_statistics()

    def run_batch_test(self, num_cycles: int = 5) -> None:
        """
        Run a batch test with specified number of cycles.

        Args:
            num_cycles: Number of cycles to run
        """
        logger.info(f"🧪 Running batch test: {num_cycles} cycles")

        for i in range(num_cycles):
            logger.info(f"\n--- Cycle {i + 1}/{num_cycles} ---")
            self.run_single_cycle()

            if i < num_cycles - 1:  # Don't sleep after last cycle
                sleep_time = 3  # Reduzido de 5 para 3 segundos para testes
                logger.info(f"💤 Test sleep: {sleep_time}s")
                time.sleep(sleep_time)

        logger.info("\n🧪 Batch test completed")
        self.print_statistics()

    def print_statistics(self) -> None:
        """Print current streaming statistics."""
        extraction_rate = (
            (self.successful_extractions / self.total_extractions * 100)
            if self.total_extractions > 0
            else 0
        )
        upload_rate = (
            (self.successful_uploads / self.total_uploads * 100)
            if self.total_uploads > 0
            else 0
        )

        logger.info("\n📈 Streaming Statistics:")
        logger.info(
            f"   Extractions: {self.successful_extractions}/{self.total_extractions} ({extraction_rate:.1f}%)"
        )
        logger.info(
            f"   Uploads: {self.successful_uploads}/{self.total_uploads} ({upload_rate:.1f}%)"
        )

    def health_check(self) -> dict:
        """
        Perform health check on all components.

        Returns:
            Health check results
        """
        logger.info("🏥 Performing health check...")

        # Test extractor
        test_data = self.extractor.extract_current_price()
        extractor_healthy = test_data is not None

        # Test loader
        loader_health = self.loader.health_check()
        loader_healthy = loader_health.get("status") == "healthy"

        overall_health = extractor_healthy and loader_healthy

        results = {
            "overall_healthy": overall_health,
            "extractor_healthy": extractor_healthy,
            "loader_healthy": loader_healthy,
            "loader_details": loader_health,
            "test_price": test_data.get("price_brl") if test_data else None,
        }

        status_emoji = "✅" if overall_health else "❌"
        logger.info(
            f"{status_emoji} Health check completed: {'Healthy' if overall_health else 'Issues detected'}"
        )

        return results


def create_streaming_controller(stream_name: str, **kwargs) -> StreamingController:
    """Create and return a StreamingController instance."""
    return StreamingController(firehose_stream_name=stream_name, **kwargs)


if __name__ == "__main__":
    # Example usage and testing
    import os
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    # Get stream name from environment
    stream_name = os.getenv("FIREHOSE_STREAM_NAME", "btcExample1")

    # Create controller
    controller = create_streaming_controller(
        stream_name=stream_name,
        extraction_interval=8,  # Ajustado para 8s (range 8-11s)
        max_retries=3,  # Aumentado para rate limiting
    )

    print("🎮 Streaming Controller Demo")
    print("Choose an option:")
    print("1. Health check")
    print("2. Single cycle test")
    print("3. Batch test (5 cycles)")
    print("4. Continuous streaming (10 minutes)")
    print("5. Continuous streaming (infinite)")

    choice = input("\nEnter choice (1-5): ").strip()

    if choice == "1":
        health = controller.health_check()
        print("\n🏥 Health Check Results:")
        for key, value in health.items():
            print(f"   {key}: {value}")

    elif choice == "2":
        print("\n🔄 Running single cycle...")
        success = controller.run_single_cycle()
        print(f"Result: {'✅ Success' if success else '❌ Failed'}")

    elif choice == "3":
        controller.run_batch_test(num_cycles=5)

    elif choice == "4":
        controller.run_continuous_streaming(duration_hours=10 / 60)  # 10 minutes

    elif choice == "5":
        controller.run_continuous_streaming()

    else:
        print("❌ Invalid choice")
