import ccxt
import os
import sys
import json
import ta
from datetime import datetime
import time
import config
import logging

sys.path.append(config.PATH_UTILITIES)
from bybit_client_old import BybitClient
from tracker_file import TrackerFile

SLEEP_TIME = 2
TRIGGER_PRICE_DELTA = 0.005  # what I use for a 1h timeframe

def __init__(self, broker_client, tracker_file, params):
    self.broker_client = broker_client
    self.tracker_file = tracker_file
    self.params = params


def run(self):
    cancel_open_orders(self.broker_client, self.params['symbol'])
    data = fetch_ohlcv_data(self.broker_client, self.params)
    manage_positions(self.broker_client, self.params, self.tracker_file)
    balance = self.broker_client.fetch_balance()['USDT']['total'] * self.params['balance_fraction']
    place_orders(self.broker_client, data, self.params, balance)
    logging.info("Execution completed successfully.")

def cancel_open_orders(broker_client, symbol):
    """Cancel all open orders and trigger orders."""
    orders = broker_client.fetch_open_orders(symbol)
    for order in orders:
        broker_client.cancel_order(order['id'], symbol)
        time.sleep(SLEEP_TIME)
    trigger_orders = broker_client.fetch_open_trigger_orders(symbol)
    for order in trigger_orders:
        broker_client.cancel_trigger_order(order['id'], symbol)
    logging.info("Open orders canceled.")

def fetch_ohlcv_data(client, params):
    """Fetch OHLCV data and calculate indicators."""
    data = client.fetch_recent_ohlcv(params['symbol'], params['timeframe'], 100).iloc[:-1]
    if params['average_type'] == 'DCM':
        ta_obj = ta.volatility.DonchianChannel(data['high'], data['low'], data['close'], window=params['average_period'])
        data['average'] = ta_obj.donchian_channel_mband()
    else:
        data['average'] = ta.trend.sma_indicator(data['close'], window=params['average_period'])
    logging.info("Fetched OHLCV data and calculated indicators.")
    return data

def manage_positions(broker_client, params, tracker_file):
    """Handle open positions, close if necessary, and manage stop loss."""
    positions = broker_client.fetch_open_positions(params['symbol'])
    if positions:
        latest_position = sorted(positions, key=lambda x: x['timestamp'], reverse=True)[0]
        logging.info(f"Open position: {latest_position}")
    else:
        logging.info("No open positions.")

def place_orders(broker_client, data, params, balance):
    """Place long and short orders based on the strategy."""
    for i, e in enumerate(params['envelopes']):
        entry_price = data[f'band_low_{i + 1}'].iloc[-1]
        trigger_price = entry_price * (1 + params['trigger_price_delta'])
        amount = balance / len(params['envelopes']) / entry_price
        if amount >= broker_client.fetch_min_amount_tradable(params['symbol']):
            broker_client.place_trigger_limit_order(params['symbol'], 'buy', amount, trigger_price, entry_price)
            logging.info(f"Placed buy order at {entry_price}")
