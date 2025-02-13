import ccxt
import os
import sys
import json
import ta
from datetime import datetime
import time
import config
import logging

class StrategyLogic:
    SLEEP_TIME = 2
    TRIGGER_PRICE_DELTA = 0.005  # Default for a 1h timeframe

    def __init__(self, broker_client, tracker_file, params):
        self.broker_client = broker_client
        self.tracker_file = tracker_file
        self.params = params
        self.trigger_price_delta = params.get('trigger_price_delta', self.TRIGGER_PRICE_DELTA)

    def run(self):
        self.cancel_open_orders()
        data = self.fetch_ohlcv_data()
        self.manage_positions()
        balance = self.broker_client.fetch_balance()['USDT']['total'] * self.params['balance_fraction']
        self.place_orders(data, balance)
        logging.info("Execution completed successfully.")

    def cancel_open_orders(self):
        """Cancel all open orders and trigger orders."""
        orders = self.broker_client.fetch_open_orders(self.params['symbol'])
        for order in orders:
            self.broker_client.cancel_order(order['id'], self.params['symbol'])
            time.sleep(self.SLEEP_TIME)
        trigger_orders = self.broker_client.fetch_open_trigger_orders(self.params['symbol'])
        for order in trigger_orders:
            self.broker_client.cancel_trigger_order(order['id'], self.params['symbol'])
        logging.info("Open orders canceled.")

    def fetch_ohlcv_data(self):
        """Fetch OHLCV data and calculate indicators."""
        ohlcv = self.broker_client.fetch_ohlcv(self.params['symbol'], self.params['timeframe'], 100)
        data = self.format_ohlcv_data(ohlcv)
        data = self.format_ohlcv_data(data)

        if self.params['average_type'] == 'DCM':
            ta_obj = ta.volatility.DonchianChannel(data['high'], data['low'], data['close'],
                                                   window=self.params['average_period'])
            data['band_low_1'] = ta_obj.donchian_channel_lband()
            data['band_low_2'] = ta_obj.donchian_channel_mband()  # Optional, if needed
            data['band_low_3'] = ta_obj.donchian_channel_hband()  # Updated to 'hband' for high band
            logging.info("Donchian Channel bands calculated.")
        else:
            data['average'] = ta.trend.sma_indicator(data['close'], window=self.params['average_period'])
            logging.info("Simple Moving Average calculated.")

        logging.info("Fetched OHLCV data and calculated indicators.")
        return data

    def format_ohlcv_data(self, ohlcv):
        """Format raw OHLCV data into a structured DataFrame."""
        import pandas as pd
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def manage_positions(self):
        """Handle open positions, close if necessary, and manage stop loss."""
        positions = self.broker_client.fetch_open_positions(self.params['symbol'])
        if positions:
            latest_position = sorted(positions, key=lambda x: x['timestamp'], reverse=True)[0]
            logging.info(f"Open position: {latest_position}")
        else:
            logging.info("No open positions.")

    def place_orders(self, data, balance):
        """Place long and short orders based on the strategy."""
        current_price = self.broker_client.fetch_ticker(self.params['symbol'])['last']

        for i, e in enumerate(self.params['envelopes']):
            if f'band_low_{i + 1}' not in data.columns:
                logging.warning(f"band_low_{i + 1} is missing in data, skipping order placement.")
                continue

            entry_price = data[f'band_low_{i + 1}'].iloc[-1]
            trigger_price = entry_price * (1 + self.trigger_price_delta)

            # Adjust trigger_price to be higher than current price for buy orders
            if trigger_price <= current_price:
                trigger_price = current_price * 1.01  # Set trigger price to 1% above current price

            amount = balance / len(self.params['envelopes']) / entry_price
            min_amount = self.broker_client.fetch_min_amount_tradable(self.params['symbol'])

            if amount >= min_amount:
                self.broker_client.place_trigger_limit_order(
                    self.params['symbol'], 'buy', amount, trigger_price, entry_price
                )
                logging.info(f"Placed buy order at {entry_price} with trigger price at {trigger_price}")
            else:
                logging.warning(f"Amount {amount} is less than minimum tradable amount.")