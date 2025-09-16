"""
Athena Query Engine for Bitcoin Analytics.

This module provides a convenient interface to execute analytical queries
against the Bitcoin streaming data stored in S3 via Athena.
"""

import time
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timezone

try:
    import boto3
    import pandas as pd

    HAS_BOTO3 = True
    HAS_PANDAS = True
except ImportError:
    try:
        import boto3

        HAS_BOTO3 = True
        HAS_PANDAS = False
    except ImportError:
        HAS_BOTO3 = False
        HAS_PANDAS = False


class AthenaQueryEngine:
    """
    Executes analytical queries on Bitcoin data using AWS Athena.

    Features:
    - Async query execution with result polling
    - Automatic result formatting (JSON, DataFrame)
    - Built-in query templates for common analytics
    - Error handling and logging
    """

    def __init__(
        self,
        database: str = "default",
        output_location: Optional[str] = None,
        region: str = "us-east-1",
    ):
        """
        Initialize Athena client.

        Args:
            database: Athena database name
            output_location: S3 location for query results
            region: AWS region
        """
        if not HAS_BOTO3:
            raise ImportError(
                "boto3 is required for AthenaQueryEngine. Install with: pip install boto3"
            )

        import boto3

        self.client = boto3.client("athena", region_name=region)
        self.database = database
        self.output_location = (
            output_location or "s3://your-athena-results-bucket/queries/"
        )
        self.region = region

        # Load SQL templates
        self.sql_templates = self._load_sql_templates()

    def _load_sql_templates(self) -> Dict[str, str]:
        """Load SQL query templates from files."""
        templates = {}
        sql_dir = Path(__file__).parent.parent.parent.parent / "sql"

        if sql_dir.exists():
            for sql_file in sql_dir.glob("*.sql"):
                templates[sql_file.stem] = sql_file.read_text(encoding="utf-8")

        return templates

    def execute_query(
        self, query: str, wait_for_completion: bool = True, max_wait_time: int = 300
    ) -> Dict[str, Any]:
        """
        Execute a query in Athena.

        Args:
            query: SQL query string
            wait_for_completion: Whether to wait for query completion
            max_wait_time: Maximum time to wait in seconds

        Returns:
            Dict with execution_id, status, and results (if completed)
        """
        try:
            # Start query execution
            response = self.client.start_query_execution(
                QueryString=query,
                QueryExecutionContext={"Database": self.database},
                ResultConfiguration={"OutputLocation": self.output_location},
            )

            execution_id = response["QueryExecutionId"]

            if not wait_for_completion:
                return {
                    "execution_id": execution_id,
                    "status": "RUNNING",
                    "message": "Query submitted successfully",
                }

            # Wait for completion
            return self._wait_for_query_completion(execution_id, max_wait_time)

        except Exception as e:
            return {
                "execution_id": None,
                "status": "FAILED",
                "error": str(e),
                "message": f"Query execution failed: {str(e)}",
            }

    def _wait_for_query_completion(
        self, execution_id: str, max_wait_time: int
    ) -> Dict[str, Any]:
        """Wait for query completion and return results."""
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            try:
                response = self.client.get_query_execution(
                    QueryExecutionId=execution_id
                )
                status = response["QueryExecution"]["Status"]["State"]

                if status == "SUCCEEDED":
                    results = self._get_query_results(execution_id)
                    return {
                        "execution_id": execution_id,
                        "status": "SUCCEEDED",
                        "results": results,
                        "execution_time_seconds": time.time() - start_time,
                    }

                elif status == "FAILED":
                    error_msg = response["QueryExecution"]["Status"].get(
                        "StateChangeReason", "Unknown error"
                    )
                    return {
                        "execution_id": execution_id,
                        "status": "FAILED",
                        "error": error_msg,
                        "execution_time_seconds": time.time() - start_time,
                    }

                elif status == "CANCELLED":
                    return {
                        "execution_id": execution_id,
                        "status": "CANCELLED",
                        "execution_time_seconds": time.time() - start_time,
                    }

                # Still running, wait a bit
                time.sleep(1)

            except Exception as e:
                return {
                    "execution_id": execution_id,
                    "status": "ERROR",
                    "error": str(e),
                    "execution_time_seconds": time.time() - start_time,
                }

        # Timeout
        return {
            "execution_id": execution_id,
            "status": "TIMEOUT",
            "message": f"Query exceeded maximum wait time of {max_wait_time} seconds",
        }

    def _get_query_results(self, execution_id: str) -> List[Dict[str, Any]]:
        """Retrieve and format query results."""
        try:
            paginator = self.client.get_paginator("get_query_results")
            page_iterator = paginator.paginate(QueryExecutionId=execution_id)

            results = []
            column_names = None

            for page in page_iterator:
                rows = page["ResultSet"]["Rows"]

                # First row contains column names
                if column_names is None and rows:
                    column_names = [col["VarCharValue"] for col in rows[0]["Data"]]
                    rows = rows[1:]  # Skip header row

                # Process data rows
                if column_names:
                    for row in rows:
                        row_data = {}
                        for i, col_name in enumerate(column_names):
                            cell_data = row["Data"][i]
                            # Handle different data types
                            if "VarCharValue" in cell_data:
                                row_data[col_name] = cell_data["VarCharValue"]
                            else:
                                row_data[col_name] = None
                        results.append(row_data)

            return results

        except Exception as e:
            raise Exception(f"Failed to retrieve query results: {str(e)}")

    def get_latest_bitcoin_data(self, hours: int = 24) -> Dict[str, Any]:
        """Get latest Bitcoin data for the specified number of hours."""
        query = f"""
        SELECT 
            price_brl,
            coleta,
            ts_ms,
            dt,
            hr
        FROM bitcoin_streaming 
        WHERE dt >= date_format(current_date - interval '{hours}' hour, '%Y-%m-%d')
        ORDER BY ts_ms DESC 
        LIMIT 100
        """

        return self.execute_query(query)

    def get_price_summary(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Get price summary for a specific date (default: today)."""
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        query = f"""
        SELECT 
            dt,
            COUNT(*) as total_records,
            MIN(price_brl) as min_price,
            MAX(price_brl) as max_price,
            AVG(price_brl) as avg_price,
            STDDEV(price_brl) as price_volatility
        FROM bitcoin_streaming 
        WHERE dt = '{date}'
        GROUP BY dt
        """

        return self.execute_query(query)

    def get_hourly_trends(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Get hourly price trends for a specific date."""
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        query = f"""
        SELECT 
            dt,
            hr,
            COUNT(*) as records,
            AVG(price_brl) as avg_price,
            MIN(price_brl) as min_price,
            MAX(price_brl) as max_price
        FROM bitcoin_streaming 
        WHERE dt = '{date}'
        GROUP BY dt, hr
        ORDER BY hr
        """

        return self.execute_query(query)

    def detect_price_spikes(
        self, date: Optional[str] = None, z_threshold: float = 2.0
    ) -> Dict[str, Any]:
        """Detect price spikes using Z-score analysis."""
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        query = f"""
        WITH price_stats AS (
            SELECT 
                AVG(price_brl) as mean_price,
                STDDEV(price_brl) as std_price
            FROM bitcoin_streaming 
            WHERE dt = '{date}'
        ),
        outliers AS (
            SELECT 
                b.*,
                p.mean_price,
                p.std_price,
                ABS(b.price_brl - p.mean_price) / p.std_price as z_score
            FROM bitcoin_streaming b
            CROSS JOIN price_stats p
            WHERE b.dt = '{date}'
        )
        SELECT 
            coleta,
            price_brl,
            z_score,
            CASE 
                WHEN z_score > {z_threshold} THEN 'SPIKE_HIGH'
                WHEN z_score < -{z_threshold} THEN 'SPIKE_LOW'
                ELSE 'NORMAL'
            END as spike_type
        FROM outliers
        WHERE z_score > {z_threshold * 0.75}
        ORDER BY z_score DESC
        """

        return self.execute_query(query)

    def to_dataframe(self, query_result: Dict[str, Any]) -> Optional[Any]:
        """Convert query results to pandas DataFrame."""
        if not HAS_PANDAS:
            raise ImportError(
                "pandas is required for to_dataframe. Install with: pip install pandas"
            )

        if query_result.get("status") != "SUCCEEDED" or not query_result.get("results"):
            return None

        try:
            import pandas as pd

            df = pd.DataFrame(query_result["results"])

            # Convert data types
            for col in df.columns:
                if (
                    "price" in col.lower()
                    or "avg" in col.lower()
                    or "min" in col.lower()
                    or "max" in col.lower()
                ):
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                elif "ts_ms" in col.lower():
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                elif "coleta" in col.lower():
                    df[col] = pd.to_datetime(df[col], errors="coerce")

            return df

        except Exception as e:
            print(f"Error converting to DataFrame: {e}")
            return None

    def execute_template_query(self, template_name: str, **kwargs) -> Dict[str, Any]:
        """Execute a predefined SQL template with parameters."""
        if template_name not in self.sql_templates:
            return {
                "status": "FAILED",
                "error": f"Template {template_name} not found",
                "available_templates": list(self.sql_templates.keys()),
            }

        try:
            query = self.sql_templates[template_name].format(**kwargs)
            return self.execute_query(query)
        except KeyError as e:
            return {
                "status": "FAILED",
                "error": f"Missing parameter: {e}",
                "template": template_name,
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "error": f"Template execution failed: {e}",
                "template": template_name,
            }


# Convenience function for quick usage
def create_athena_engine(
    database: str = "default",
    output_location: Optional[str] = None,
    region: str = "us-east-1",
) -> AthenaQueryEngine:
    """Create and return an AthenaQueryEngine instance."""
    return AthenaQueryEngine(database, output_location, region)


if __name__ == "__main__":
    # Example usage
    try:
        engine = create_athena_engine()

        # Test connection with a simple query
        print("🔍 Testing Athena connection...")
        result = engine.get_latest_bitcoin_data(hours=1)

        if result["status"] == "SUCCEEDED":
            print(f"✅ Success! Found {len(result['results'])} records")
            if result["results"]:
                print("📊 Sample data:")
                for i, record in enumerate(result["results"][:3]):
                    print(
                        f"   {i + 1}. Price: R$ {record.get('price_brl', 'N/A')} at {record.get('coleta', 'N/A')}"
                    )
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Install dependencies: pip install boto3 pandas")
