"""
AWS Firehose Loader for Stream-Bit project.

This module handles uploading streaming data to AWS Kinesis Data Firehose.
Focuses purely on the loading aspect, receiving formatted data and sending to AWS.
"""

import json
import boto3
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Setup logging
logger = logging.getLogger(__name__)


class FirehoseLoader:
    """
    Handles data upload to AWS Kinesis Data Firehose.

    Responsibilities:
    - Initialize Firehose client with credentials
    - Format data for Firehose (JSON + newline)
    - Send records to Firehose stream
    - Handle errors and retries
    - Log delivery status
    """

    def __init__(
        self,
        stream_name: str,
        region: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        """
        Initialize Firehose loader.

        Args:
            stream_name: Name of the Firehose delivery stream
            region: AWS region
            aws_access_key_id: AWS access key (optional, can use env vars)
            aws_secret_access_key: AWS secret key (optional, can use env vars)
        """
        self.stream_name = stream_name
        self.region = region

        # Initialize Firehose client
        client_config = {"region_name": region}

        if aws_access_key_id and aws_secret_access_key:
            client_config.update(
                {
                    "aws_access_key_id": aws_access_key_id,
                    "aws_secret_access_key": aws_secret_access_key,
                }
            )

        try:
            self.client = boto3.client("firehose", **client_config)
            logger.info(f"Firehose client initialized for stream: {stream_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Firehose client: {e}")
            raise

    def send_record(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a single record to Firehose.

        Args:
            data: Dictionary containing the data to send

        Returns:
            Dict with status, record_id, and metadata
        """
        try:
            # Format data as JSON with newline (Firehose requirement)
            json_data = json.dumps(data, ensure_ascii=False)
            data_bytes = (json_data + "\n").encode("utf-8")

            # Send to Firehose
            response = self.client.put_record(
                DeliveryStreamName=self.stream_name, Record={"Data": data_bytes}
            )

            # Extract response metadata
            result = {
                "status": "success",
                "record_id": response.get("RecordId", "unknown"),
                "encrypted": response.get("Encrypted", False),
                "http_status": response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode", "unknown"
                ),
                "timestamp": datetime.utcnow().isoformat(),
                "data_size_bytes": len(data_bytes),
            }
            return result

        except Exception as e:
            # Handle all types of errors with detailed logging
            error_result = {
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__,
                "timestamp": datetime.utcnow().isoformat(),
                "stream_name": self.stream_name,
                "data_preview": str(data)[:200] + "..."
                if len(str(data)) > 200
                else str(data),
            }

            # Enhanced error logging
            logger.error(f"❌ Failed to send record: {type(e).__name__}: {e}")
            logger.error(f"🔍 Stream: {self.stream_name}")
            logger.error(f"🔍 Data size: {len(str(data))} characters")
            logger.error(f"🔍 Data preview: {str(data)[:100]}...")

            # Log AWS-specific error details if available
            if hasattr(e, "response"):
                try:
                    response = getattr(e, "response")
                    if isinstance(response, dict):
                        error_info = response.get("Error", {})
                        if error_info:
                            logger.error(
                                f"🔍 AWS Error Code: {error_info.get('Code', 'unknown')}"
                            )
                            logger.error(
                                f"🔍 AWS Error Message: {error_info.get('Message', 'unknown')}"
                            )

                        http_status = response.get("ResponseMetadata", {}).get(
                            "HTTPStatusCode"
                        )
                        if http_status:
                            logger.error(f"🔍 HTTP Status: {http_status}")
                            error_result["http_status"] = http_status
                except Exception:
                    pass  # Ignore errors in error handling

            return error_result

    def send_batch(self, records: list[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Send multiple records to Firehose in batch.

        Args:
            records: List of dictionaries to send

        Returns:
            Dict with batch status and individual results
        """
        if not records:
            return {"status": "failed", "error": "No records provided"}

        try:
            # Format records for batch
            firehose_records = []
            for record in records:
                json_data = json.dumps(record, ensure_ascii=False)
                data_bytes = (json_data + "\n").encode("utf-8")
                firehose_records.append({"Data": data_bytes})

            # Send batch to Firehose
            response = self.client.put_record_batch(
                DeliveryStreamName=self.stream_name, Records=firehose_records
            )

            # Process batch response
            failed_count = response.get("FailedPutCount", 0)
            successful_count = len(records) - failed_count

            result = {
                "status": "success" if failed_count == 0 else "partial",
                "total_records": len(records),
                "successful_count": successful_count,
                "failed_count": failed_count,
                "timestamp": datetime.utcnow().isoformat(),
                "http_status": response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode", "unknown"
                ),
            }

            # Log failures if any
            if failed_count > 0:
                failed_records = []
                for i, record_result in enumerate(response.get("RequestResponses", [])):
                    if "ErrorCode" in record_result:
                        failed_records.append(
                            {
                                "index": i,
                                "error_code": record_result["ErrorCode"],
                                "error_message": record_result.get(
                                    "ErrorMessage", "Unknown error"
                                ),
                            }
                        )
                result["failed_records"] = failed_records
                logger.warning(
                    f"⚠️ Batch partially failed: {failed_count}/{len(records)} records failed"
                )
            else:
                logger.info(f"✅ Batch sent successfully: {successful_count} records")

            return result

        except Exception as e:
            error_result = {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
                "total_records": len(records),
            }
            logger.error(f"❌ Failed to send batch: {e}")
            return error_result

    def health_check(self) -> Dict[str, Any]:
        """
        Check if Firehose stream is accessible and healthy.

        Returns:
            Dict with health status
        """
        try:
            # Try to describe the delivery stream
            response = self.client.describe_delivery_stream(
                DeliveryStreamName=self.stream_name
            )

            stream_status = response["DeliveryStreamDescription"][
                "DeliveryStreamStatus"
            ]

            result = {
                "status": "healthy" if stream_status == "ACTIVE" else "unhealthy",
                "stream_name": self.stream_name,
                "stream_status": stream_status,
                "timestamp": datetime.utcnow().isoformat(),
            }

            if stream_status == "ACTIVE":
                logger.info(f"✅ Firehose stream is healthy: {self.stream_name}")
            else:
                logger.warning(f"⚠️ Firehose stream status: {stream_status}")

            return result

        except Exception as e:
            error_result = {
                "status": "unhealthy",
                "error": str(e),
                "stream_name": self.stream_name,
                "timestamp": datetime.utcnow().isoformat(),
            }
            logger.error(f"❌ Firehose health check failed: {e}")
            return error_result


def create_firehose_loader(
    stream_name: str,
    region: str = "us-east-1",
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
) -> FirehoseLoader:
    """Create and return a FirehoseLoader instance."""
    return FirehoseLoader(stream_name, region, aws_access_key_id, aws_secret_access_key)


def create_firehose_loader_from_env() -> FirehoseLoader:
    """Create FirehoseLoader using environment variables."""
    stream_name = os.getenv("FIREHOSE_STREAM_NAME")
    if not stream_name:
        raise ValueError("FIREHOSE_STREAM_NAME environment variable is required")

    return FirehoseLoader(
        stream_name=stream_name,
        region=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


if __name__ == "__main__":
    # Example usage
    try:
        # Create loader from environment variables
        loader = create_firehose_loader_from_env()

        # Health check
        health = loader.health_check()
        print(f"Health Status: {health['status']}")

        # Test record
        test_data = {
            "price_brl": 615000.0,
            "coleta": "2025-09-12T15:30:00Z",
            "ts_ms": 1726154580000,
            "currency": "BRL",
        }

        result = loader.send_record(test_data)
        print(f"Send Result: {result['status']}")

    except Exception as e:
        print(f"❌ Example failed: {e}")
        print("💡 Set environment variables:")
        print("   FIREHOSE_STREAM_NAME=your_stream_name")
        print("   AWS_ACCESS_KEY_ID=your_key")
        print("   AWS_SECRET_ACCESS_KEY=your_secret")
        print("   AWS_REGION=your_region")
