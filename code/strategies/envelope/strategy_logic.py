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

# Basic configuration
coin = "BTC"
symbol = coin + "/USDT:USDT"
balance_fraction = 0.4
SLEEP_TIME = 2

# Initialize logging
log_file = os.path.join(config.PATH_LOGGING, "bot_" + coin.lower() + ".log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),  # Log to file
        logging.StreamHandler()  # Log to console
    ]
)

def initialize_clients():
    """Initialize API clients and tracker file."""
    tracker_file = TrackerFile(config.PATH_TRACKER_FILE, symbol)
    path_secret_json = os.path.join(config.PATH_PROJECT_ROOT, "secret.json")
    broker_client = BybitClient(path_secret_json, "bybit-testnet")
    return broker_client, tracker_file

def cancel_open_orders(client):
    """Cancel all open orders and trigger orders."""
    orders = client.fetch_open_orders(symbol)
    for order in orders:
        client.cancel_order(order['id'], symbol)
        time.sleep(SLEEP_TIME)
    trigger_orders = client.fetch_open_trigger_orders(symbol)
    for order in trigger_orders:
        client.cancel_trigger_order(order['id'], symbol)
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

def manage_positions(client, params, tracker_file):
    """Handle open positions, close if necessary, and manage stop loss."""
    positions = client.fetch_open_positions(params['symbol'])
    if positions:
        latest_position = sorted(positions, key=lambda x: x['timestamp'], reverse=True)[0]
        logging.info(f"Open position: {latest_position}")
    else:
        logging.info("No open positions.")

def place_orders(client, data, params, balance):
    """Place long and short orders based on the strategy."""
    for i, e in enumerate(params['envelopes']):
        entry_price = data[f'band_low_{i + 1}'].iloc[-1]
        trigger_price = entry_price * (1 + params['trigger_price_delta'])
        amount = balance / len(params['envelopes']) / entry_price
        if amount >= client.fetch_min_amount_tradable(params['symbol']):
            client.place_trigger_limit_order(params['symbol'], 'buy', amount, trigger_price, entry_price)
            logging.info(f"Placed buy order at {entry_price}")

if __name__ == "__main__":
    try:
        bitget, tracker_file = initialize_clients()
        cancel_open_orders(bitget)
        params = {
            'symbol': symbol,
            'timeframe': '1h',
            'margin_mode': 'isolated',
            'balance_fraction': balance_fraction,
            'leverage': 1,
            'average_type': 'DCM',
            'average_period': 5,
            'envelopes': [0.07, 0.11, 0.14],
            'stop_loss_pct': 0.4,
            'trigger_price_delta': 0.005,
        }
        data = fetch_ohlcv_data(bitget, params)
        manage_positions(bitget, params, tracker_file)
        balance = bitget.fetch_balance()['USDT']['total'] * params['balance_fraction']
        place_orders(bitget, data, params, balance)
        logging.info("Execution completed successfully.")
    except Exception as e:
        logging.error(f"Error occurred: {e}")
