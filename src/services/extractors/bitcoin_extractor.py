"""
Bitcoin Price Extractor.

This module focuses purely on extracting Bitcoin price data from CoinGecko API.
Clean separation of concerns: only handles data extraction, not uploading.
"""

import requests
import datetime
import time
import random
import logging
from typing import Optional, Dict, Any

# Setup logging
logger = logging.getLogger(__name__)


class BitcoinExtractor:
    """
    Extracts Bitcoin price data from CoinGecko API.

    Responsibilities:
    - Make API calls to CoinGecko
    - Handle rate limiting and retries
    - Format extracted data consistently
    - Provide error handling and logging
    """

    def __init__(
        self,
        base_url: str = "https://api.coingecko.com/api/v3",
        timeout: int = 10,
        user_agent: str = "stream-bit/1.0 (Educational Purpose)",
    ):
        """
        Initialize Bitcoin extractor.

        Args:
            base_url: CoinGecko API base URL
            timeout: Request timeout in seconds
            user_agent: User agent for API requests
        """
        self.base_url = base_url
        self.timeout = timeout
        self.headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }

        logger.info("Bitcoin extractor initialized")

    def extract_current_price(
        self, coin: str = "bitcoin", currency: str = "brl"
    ) -> Optional[Dict[str, Any]]:
        """
        Extract current Bitcoin price from CoinGecko.

        Args:
            coin: Cryptocurrency ID (default: bitcoin)
            currency: Target currency (default: brl)

        Returns:
            Dict with extracted data or None if failed
        """
        try:
            # Build API URL
            url = f"{self.base_url}/simple/price"
            params = {"ids": coin, "vs_currencies": currency}

            # Make API request
            logger.debug(f"Making API request to: {url}")
            response = requests.get(
                url, headers=self.headers, params=params, timeout=self.timeout
            )
            response.raise_for_status()

            # Parse JSON response
            data = response.json()

            # Extract price
            if coin in data and currency in data[coin]:
                raw_price = data[coin][currency]

                # Create optimized data structure for Hive partitioning
                # Using minimal fields for better performance in Athena
                extracted_data = {
                    "price_brl": float(raw_price),
                    "coleta": datetime.datetime.now(datetime.timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "ts_ms": int(
                        time.time() * 1000
                    ),  # For Hive partitioning: dt=YYYY-MM-DD/hr=HH
                    "currency": currency.upper(),
                }

                logger.info(f"✅ Price extracted: R$ {raw_price:,.2f}")
                return extracted_data
            else:
                logger.error(
                    f"❌ Price not found in API response for {coin}/{currency}"
                )
                return None

        except requests.exceptions.Timeout:
            logger.error(f"❌ Request timeout after {self.timeout}s")
            return None
        except requests.exceptions.HTTPError as e:
            if "429" in str(e):
                logger.warning("⚠️ Rate limited by CoinGecko API")
            else:
                logger.error(f"❌ HTTP error: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Request error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error during extraction: {e}")
            return None

    def extract_with_retry(
        self,
        max_retries: int = 3,
        base_delay: int = 10,  # Voltou para 5s como base
        **kwargs,
    ) -> Optional[Dict[str, Any]]:
        """
        Extract price with retry logic.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries (seconds) - starts fast, increases gradually
            **kwargs: Arguments passed to extract_current_price()

        Returns:
            Extracted data or None if all retries failed
        """
        for attempt in range(max_retries + 1):
            try:
                result = self.extract_current_price(**kwargs)
                if result is not None:
                    return result

                if attempt < max_retries:
                    # Backoff gradual inteligente: 5-10s, 10-20s, 20-30s
                    if attempt == 0:  # Primeiro retry: rápido
                        delay = base_delay + random.uniform(0, 5)  # 5-10s
                    elif attempt == 1:  # Segundo retry: médio
                        delay = base_delay * 2 + random.uniform(0, 10)  # 10-20s
                    else:  # Terceiro retry em diante: mais longo
                        delay = base_delay * 4 + random.uniform(0, 10)  # 20-30s

                    logger.info(f"⏳ Retry {attempt + 1}/{max_retries} in {delay:.1f}s")
                    time.sleep(delay)

            except Exception as e:
                logger.error(f"❌ Retry attempt {attempt + 1} failed: {e}")
                if attempt < max_retries:
                    # Mesmo padrão para exceptions
                    if attempt == 0:
                        delay = base_delay + random.uniform(0, 5)  # 5-10s
                    elif attempt == 1:
                        delay = base_delay * 2 + random.uniform(0, 10)  # 10-20s
                    else:
                        delay = base_delay * 4 + random.uniform(0, 10)  # 20-30s
                    time.sleep(delay)

        logger.error(f"❌ All {max_retries + 1} extraction attempts failed")
        return None

    def get_recommended_sleep_time(
        self,
        success: bool,
        base_interval: int = 6,  # Reduzido de 8 para 6 segundos para target 8-11s
    ) -> int:
        """
        Get recommended sleep time based on extraction success.

        Args:
            success: Whether the last extraction was successful
            base_interval: Base interval in seconds (increased for rate limiting)

        Returns:
            Recommended sleep time in seconds
        """
        if success:
            # Sleep otimizado para 8-11 segundos total
            return base_interval + random.randint(1, 4)  # 6 + 2-5 = 8-11 segundos
        else:
            # Sleep mais longo apenas para failures por rate limiting
            return base_interval + random.randint(10, 20)  # base + 10-20s para falhas


def create_bitcoin_extractor(**kwargs) -> BitcoinExtractor:
    """Create and return a BitcoinExtractor instance."""
    return BitcoinExtractor(**kwargs)


if __name__ == "__main__":
    # Example usage
    extractor = create_bitcoin_extractor()

    print("🔍 Testing Bitcoin extraction...")

    # Simple extraction
    data = extractor.extract_current_price()
    if data:
        print(f"✅ Extracted: R$ {data['price_brl']:,.2f} at {data['coleta']}")
        print(f"📊 Data structure: {list(data.keys())}")
    else:
        print("❌ Extraction failed")

    # Extraction with retry
    print("\n🔄 Testing extraction with retry...")
    data_retry = extractor.extract_with_retry(max_retries=2)
    if data_retry:
        print(f"✅ Retry extraction successful: R$ {data_retry['price_brl']:,.2f}")
    else:
        print("❌ Retry extraction failed")

    # Sleep time recommendation
    sleep_time = extractor.get_recommended_sleep_time(success=True)
    print(f"💤 Recommended sleep time: {sleep_time}s")
