import ccxt
import json
import time
import pandas as pd
from typing import Any, Optional, Dict, List


class BybitClient():
    def __init__(self, path_to_secret_json, secret_profile, use_real_environment=False) -> None:
        with open(path_to_secret_json, "r") as f:
            secret = json.load(f)[secret_profile]

        client_config = {
            "apiKey": secret['apiKey'],
            "secret": secret['secret'],
            "options": {"defaultType": "swap", "accountType": "UNIFIED"}  # Ensure UNIFIED is set
        }

        self.session = ccxt.bybit(client_config)
        self.session.set_sandbox_mode(not use_real_environment)

    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        try:
            return self.session.fetch_ticker(symbol)
        except Exception as e:
            raise Exception(f"Failed to fetch ticker for {symbol}: {e}")

    def fetch_min_amount_tradable(self, symbol: str) -> float:
        try:
            return self.session.markets[symbol]['limits']['amount']['min']
        except Exception as e:
            raise Exception(f"Failed to fetch minimum amount tradable: {e}")

    def amount_to_precision(self, symbol: str, amount: float) -> str:
        try:
            return self.session.amount_to_precision(symbol, amount)
        except Exception as e:
            raise Exception(f"Failed to convert amount {amount} {symbol} to precision", e)

    def price_to_precision(self, symbol: str, price: float) -> str:
        try:
            return self.session.price_to_precision(symbol, price)
        except Exception as e:
            raise Exception(f"Failed to convert price {price} to precision for {symbol}", e)

    def fetch_balance(self):
        return self.session.fetch_balance(params={"accountType": "UNIFIED"})

    def fetch_order(self, id: str, symbol: str) -> Dict[str, Any]:
        try:
            return self.session.fetch_order(id, symbol)
        except Exception as e:
            raise Exception(f"Failed to fetch order {id} info for {symbol}: {e}")

    def fetch_open_orders(self, symbol: str) -> List[Dict[str, Any]]:
        try:
            return self.session.fetch_open_orders(symbol)
        except Exception as e:
            raise Exception(f"Failed to fetch open orders: {e}")

    def fetch_open_trigger_orders(self, symbol: str) -> List[Dict[str, Any]]:
        try:
            return self.session.fetch_open_orders(symbol, params={'stop': True})
        except Exception as e:
            raise Exception(f"Failed to fetch open trigger orders: {e}")

    def fetch_closed_trigger_orders(self, symbol: str) -> List[Dict[str, Any]]:
        try:
            return self.session.fetch_closed_orders(symbol, params={'stop': True})
        except Exception as e:
            raise Exception(f"Failed to fetch closed trigger orders: {e}")

    def cancel_order(self, id: str, symbol: str) -> Dict[str, Any]:
        try:
            return self.session.cancel_order(id, symbol)
        except Exception as e:
            raise Exception(f"Failed to cancel the {symbol} order {id}", e)

    def cancel_trigger_order(self, id: str, symbol: str) -> Dict[str, Any]:
        try:
            return self.session.cancel_order(id, symbol, params={'stop': True})
        except Exception as e:
            raise Exception(f"Failed to cancel the {symbol} trigger order {id}", e)

    def fetch_open_positions(self, symbol: str) -> List[Dict[str, Any]]:
        try:
            positions = self.session.fetch_positions([symbol], params={'productType': 'USDT-FUTURES', 'marginCoin': 'USDT'})
            real_positions = [position for position in positions if float(position['contracts']) > 0]
            return real_positions
        except Exception as e:
            raise Exception(f"Failed to fetch open positions: {e}")

    def flash_close_position(self, symbol: str, side: Optional[str] = None) -> Dict[str, Any]:
        try:
            return self.session.close_position(symbol, side=side)
        except Exception as e:
            raise Exception(f"Failed to fetch closed order for {symbol}", e)

    def set_margin_mode(self, symbol: str, margin_mode: str = 'isolated') -> None:
        try:
            self.session.set_margin_mode(
                margin_mode,
                symbol,
                params={'productType': 'USDT-FUTURES', 'marginCoin': 'USDT'},
            )
        except Exception as e:
            raise Exception(f"Failed to set margin mode: {e}")

    def set_leverage(self, symbol: str, margin_mode: str = 'isolated', leverage: int = 1) -> None:
        try:
            if margin_mode == 'isolated':
                self.session.set_leverage(leverage, symbol, params={'productType': 'USDT-FUTURES', 'marginCoin': 'USDT', 'holdSide': 'long'})
                self.session.set_leverage(leverage, symbol, params={'productType': 'USDT-FUTURES', 'marginCoin': 'USDT', 'holdSide': 'short'})
            else:
                self.session.set_leverage(leverage, symbol, params={'productType': 'USDT-FUTURES', 'marginCoin': 'USDT'})
        except Exception as e:
            raise Exception(f"Failed to set leverage: {e}")

    def fetch_recent_ohlcv(self, symbol: str, timeframe: str, limit: int = 1000) -> pd.DataFrame:
        bitget_fetch_limit = 200
        timeframe_to_milliseconds = {
            '1m': 60000, '5m': 300000, '15m': 900000, '30m': 1800000, '1h': 3600000, '2h': 7200000, '4h': 14400000, '1d': 86400000,
        }
        end_timestamp = int(time.time() * 1000)
        start_timestamp = end_timestamp - (limit * timeframe_to_milliseconds[timeframe])
        current_timestamp = start_timestamp

        ohlcv_data = []
        while current_timestamp < end_timestamp:
            request_end_timestamp = min(current_timestamp + (bitget_fetch_limit * timeframe_to_milliseconds[timeframe]), end_timestamp)
            try:
                fetched_data = self.session.fetch_ohlcv(
                    symbol,
                    timeframe,
                    params={"startTime": str(current_timestamp), "endTime": str(request_end_timestamp), "limit": bitget_fetch_limit}
                )
                ohlcv_data.extend(fetched_data)
            except Exception as e:
                raise Exception(f"Failed to fetch OHLCV data for {symbol} in timeframe {timeframe}: {e}")

            current_timestamp += (bitget_fetch_limit * timeframe_to_milliseconds[timeframe]) + 1

        df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df.sort_index(inplace=True)

        return df

    def place_market_order(self, symbol: str, side: str, amount: float, reduce: bool = False) -> Dict[str, Any]:
        try:
            params = {'reduceOnly': reduce}
            amount = self.amount_to_precision(symbol, amount)
            return self.session.create_order(symbol, 'market', side, amount, params=params)
        except Exception as e:
            raise Exception(f"Failed to place market order of {amount} {symbol}: {e}")

    def place_limit_order(self, symbol: str, side: str, amount: float, price: float, reduce: bool = False) -> Dict[str, Any]:
        try:
            params = {'reduceOnly': reduce}
            amount = self.amount_to_precision(symbol, amount)
            price = self.price_to_precision(symbol, price)
            return self.session.create_order(symbol, 'limit', side, amount, price, params=params)
        except Exception as e:
            raise Exception(f"Failed to place limit order of {amount} {symbol} at price {price}: {e}")

    def place_trigger_market_order(self, symbol: str, side: str, amount: float, trigger_price: float, reduce: bool = False, print_error: bool = False) -> Optional[Dict[str, Any]]:
        try:
            amount = self.amount_to_precision(symbol, amount)
            trigger_price = self.price_to_precision(symbol, trigger_price)
            trigger_direction = self.get_trigger_direction(side)
            params = {'reduceOnly': reduce, 'triggerPrice': trigger_price, 'delegateType': 'price_fill',
                      'triggerDirection': trigger_direction}
            return self.session.create_order(symbol, 'market', side, amount, params=params)
        except Exception as err:
            if print_error:
                print(err)
                return None
            else:
                raise err

    def get_trigger_direction(self, side):
        if side == 'buy':
            return "below"
        else:
            return "above"


    def place_trigger_limit_order(self, symbol: str, side: str, amount: float, trigger_price: float, price: float, reduce: bool = False, print_error: bool = False) -> Optional[Dict[str, Any]]:
        try:
            amount = self.amount_to_precision(symbol, amount)
            trigger_price = self.price_to_precision(symbol, trigger_price)
            price = self.price_to_precision(symbol, price)
            trigger_direction = self.get_trigger_direction(side)
            params = {'reduceOnly': reduce, 'triggerPrice': trigger_price, 'delegateType': 'price_fill',
                      'triggerDirection': trigger_direction}
            return self.session.create_order(symbol, 'limit', side, amount, price, params=params)
        except Exception as err:
            if print_error:
                print(err)
                return None
            else:
                raise err

    def fetch_margin_mode(self, symbol: str) -> str:
        try:
            # Fetch margin mode using Bybit API's endpoint for position settings
            params = {'symbol': symbol}
            endpoint = '/v2/private/position/switch-mode'

            # Make the request to the private endpoint using ccxt's request method
            response = self.session.request('GET', endpoint, params=params)

            # If successful, it should return something like:
            # {'retCode': 0, 'result': {'symbol': 'ETHUSDT', 'position_mode': 'single'}}

            if response['retCode'] == 0:
                return response['result']['position_mode']
            else:
                raise ccxt.BaseError(f"Error fetching margin mode: {response.get('retMsg')}")

        except Exception as e:
            raise Exception(f"Failed to fetch margin mode for {symbol}: {e}")

    def fetch_ohlcv(self, symbol, timeframe, limit=100):
        """Wrapper for CCXT fetch_ohlcv"""
        return  self.session.fetch_ohlcv(symbol, timeframe, limit=limit)