import time
import pandas as pd
import ccxt

class CandleDataLoader:
    def __init__(self, exchange):
        self.session = exchange  # Should be an instance of ccxt.bitget (or another exchange)
        self.fetch_limit = 200
        self.timeframe_to_ms = {
            '1m': 60_000, '5m': 300_000, '15m': 900_000, '30m': 1_800_000,
            '1h': 3_600_000, '2h': 7_200_000, '4h': 14_400_000, '1d': 86_400_000,
        }

    # Fetch recent candle data also know as ohlcv
    def fetch_recent_candle_data(self, symbol: str, timeframe: str, limit: int = 1000) -> pd.DataFrame:
        """Fetch recent OHLCV data from the exchange with pagination."""
        if timeframe not in self.timeframe_to_ms:
            raise ValueError(f"Invalid timeframe: {timeframe}")

        interval_ms = self.timeframe_to_ms[timeframe]
        end_timestamp = int(time.time() * 1000)
        start_timestamp = end_timestamp - (limit * interval_ms)
        current_timestamp = start_timestamp

        ohlcv_data = []
        while current_timestamp < end_timestamp:
            request_end_timestamp = min(current_timestamp + (self.fetch_limit * interval_ms), end_timestamp)
            try:
                fetched_data = self.session.fetch_ohlcv(
                    symbol, timeframe, params={
                        "startTime": current_timestamp,
                        "endTime": request_end_timestamp,
                        "limit": self.fetch_limit
                    }
                )
                if not fetched_data:
                    break  # Stop if no data is returned

                ohlcv_data.extend(fetched_data)
            except Exception as e:
                print(f"Warning: Failed to fetch OHLCV data for {symbol} ({timeframe}): {e}")
                break  # Stop fetching on failure instead of looping indefinitely

            current_timestamp = request_end_timestamp + 1  # Avoid duplicate timestamps

        # Convert to DataFrame
        df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        if df.empty:
            raise ValueError(f"No OHLCV data fetched for {symbol} in {timeframe}")

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)

        return df
