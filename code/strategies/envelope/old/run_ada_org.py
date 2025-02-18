import ccxt
import os
import sys
import json
import ta
from datetime import datetime
import time
import config
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from utilities.bybit_client_old import BybitClient
from utilities.tracker_file import TrackerFile

# Basic configuration
sympol = "ADA/USDT:USDT"
balance_fraction = 0.5

# Initialize logging
log_file = os.path.join(config.PATH_LOGGING, 'bot_ada.log')
logging.basicConfig(
    filename=log_file,  # Path to log file
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Initialize tracker file
tracker_file = TrackerFile(config.PATH_TRACKER_FILE, sympol)

# Initialize the broker client
path_secret_json = os.path.join(config.PATH_PROJECT_ROOT, "secret.json")
broker_client = BybitClient(path_secret_json, "bybit-testnet")
bitget = broker_client

# Configuration
params = {
    'symbol': sympol,
    'timeframe': '1h',
    'margin_mode': 'isolated',  # 'cross'
    'balance_fraction': balance_fraction,
    'leverage': 1,
    'average_type': 'DCM',  # 'SMA', 'EMA', 'WMA', 'DCM'
    'average_period': 5,
    'envelopes': [0.07, 0.11, 0.14],
    'stop_loss_pct': 0.4,
    'use_longs': True,  # set to False if you want to use only shorts
    'use_shorts': True,  # set to False if you want to use only longs
}

trigger_price_delta = 0.005  # what I use for a 1h timeframe

# --- CANCEL OPEN ORDERS ---
orders = bitget.fetch_open_orders(params['symbol'])
for order in orders:
    bitget.cancel_order(order['id'], params['symbol'])

trigger_orders = bitget.fetch_open_trigger_orders(params['symbol'])
long_orders_left = 0
short_orders_left = 0
for order in trigger_orders:
    if order['side'] == 'buy' and order['info']['tradeSide'] == 'open':
        long_orders_left += 1
    elif order['side'] == 'sell' and order['info']['tradeSide'] == 'open':
        short_orders_left += 1
    bitget.cancel_trigger_order(order['id'], params['symbol'])

logging.info(f"Orders cancelled, {long_orders_left} longs left, {short_orders_left} shorts left")

# --- FETCH OHLCV DATA, CALCULATE INDICATORS ---
data = bitget.fetch_recent_ohlcv(params['symbol'], params['timeframe'], 100).iloc[:-1]

if 'DCM' == params['average_type']:
    ta_obj = ta.volatility.DonchianChannel(data['high'], data['low'], data['close'], window=params['average_period'])
    data['average'] = ta_obj.donchian_channel_mband()
elif 'SMA' == params['average_type']:
    data['average'] = ta.trend.sma_indicator(data['close'], window=params['average_period'])
elif 'EMA' == params['average_type']:
    data['average'] = ta.trend.ema_indicator(data['close'], window=params['average_period'])
elif 'WMA' == params['average_type']:
    data['average'] = ta.trend.wma_indicator(data['close'], window=params['average_period'])
else:
    raise ValueError(f"The average type {params['average_type']} is not supported")

for i, e in enumerate(params['envelopes']):
    data[f'band_high_{i + 1}'] = data['average'] / (1 - e)
    data[f'band_low_{i + 1}'] = data['average'] * (1 - e)

logging.info("OHLCV data fetched")

# --- CHECKS IF STOP LOSS WAS TRIGGERED ---
closed_orders = bitget.fetch_closed_trigger_orders(params['symbol'])
tracker_info = tracker_file.read_tracker_file()
if len(closed_orders) > 0 and closed_orders[-1]['id'] in tracker_info['stop_loss_ids']:
    tracker_file.update_tracker_file({
        "last_side": closed_orders[-1]['info']['posSide'],
        "status": "stop_loss_triggered",
        "stop_loss_ids": [],
    })
    logging.warning("Stop loss was triggered")

# --- CHECK FOR MULTIPLE OPEN POSITIONS AND CLOSE THE EARLIEST ONE ---
positions = bitget.fetch_open_positions(params['symbol'])
if positions:
    sorted_positions = sorted(positions, key=lambda x: x['timestamp'], reverse=True)
    latest_position = sorted_positions[0]
    for pos in sorted_positions[1:]:
        bitget.flash_close_position(pos['symbol'], side=pos['side'])
        logging.info(f"Double position case, closing the {pos['side']}.")

# --- CHECKS IF A POSITION IS OPEN ---
position = bitget.fetch_open_positions(params['symbol'])
open_position = True if len(position) > 0 else False
if open_position:
    position = position[0]
    logging.info(f"{position['side']} position of {round(position['contracts'] * position['contractSize'], 2)} ~ {round(position['contracts'] * position['contractSize'] * position['markPrice'], 2)} USDT is running")
else:
    logging.info("No open position currently.")

# --- OK TO TRADE CHECK ---
tracker_info = tracker_file.read_tracker_file()
logging.info(f"Okay to trade check, status was {tracker_info['status']}")
last_price = data['close'].iloc[-1]
resume_price = data['average'].iloc[-1]
logging.debug(f"Last price: {last_price}, Resume price: {resume_price}")

if tracker_info['status'] == "ok_to_trade":
    if params['use_longs'] and last_price > resume_price:
            logging.info(f"Placing long trade.")
        # Add your long trade logic here
    elif params['use_shorts'] and last_price < resume_price:
        logging.info(f"Placing short trade.")
        # Add your short trade logic here
    else:
        logging.info("Conditions not met for trade placement.")

if tracker_info['status'] != "ok_to_trade":
    logging.info(f"Not ok to trade, status is {tracker_info['status']}")
    if ('long' == tracker_info['last_side'] and last_price >= resume_price) or (
            'short' == tracker_info['last_side'] and last_price <= resume_price):
        tracker_file.update_tracker_file({"status": "ok_to_trade", "last_side": tracker_info['last_side']})
    else:
        logging.info(f"Conditions not met for resuming trade. Exiting.")
        sys.exit()

# Additional debug logging for checking all conditions
logging.debug(f"Tracker Info: {tracker_info}")
logging.debug(f"Last Price: {last_price}")
logging.debug(f"Resume Price: {resume_price}")
