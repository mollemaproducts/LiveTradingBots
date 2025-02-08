import ccxt
import os
import sys
import json
import ta
from datetime import datetime
import time  # Added for waiting between position checks

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from utilities.bybit_client_old import BybitClient

BYBIT_API_KEY = "ovZyOF03R434om5MX6"
BYBIT_API_SECRET = "Bmn9Wqn1bePh891gbpxfS5vyIW64MrXskftq"
USE_TESTNET = True  # True means your API keys were generated on testnet.bybit.com

# --- CONFIG ---
params = {
    'symbol': 'ETH/USDT:USDT',
    'timeframe': '1h',
    'margin_mode': 'isolated',  # 'cross'
    'balance_fraction': 1,
    'leverage': 1,
    'average_type': 'DCM',  # 'SMA', 'EMA', 'WMA', 'DCM'
    'average_period': 5,
    'envelopes': [0.07, 0.11, 0.14],
    'stop_loss_pct': 0.4,
    'use_longs': True,  # set to False if you want to use only shorts
    'use_shorts': True,  # set to False if you want to use only longs
}

key_path = 'LiveTradingBots/secret.json'
key_name = 'bybit_client'

tracker_file = os.path.join(os.getcwd(), 'code/strategies/envelope', f"tracker_{params['symbol'].replace('/', '-').replace(':', '-')}.json")

trigger_price_delta = 0.005  # what I use for a 1h timeframe

# --- AUTHENTICATION ---
print(f"\n{datetime.now().strftime('%H:%M:%S')}: >>> starting execution for {params['symbol']}")
client_options = {
    'apiKey': BYBIT_API_KEY,
    'secret': BYBIT_API_SECRET,
    "options": {"defaultType": "swap", "accountType": "UNIFIED"}  # Ensure UNIFIED is set
}

# Initialize Bybit client
bitget = BybitClient(client_options, USE_TESTNET)

# --- TRACKER FILE ---
if not os.path.exists(tracker_file):
    with open(tracker_file, 'w') as file:
        json.dump({"status": "ok_to_trade", "last_side": None, "stop_loss_ids": []}, file)

def read_tracker_file(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def update_tracker_file(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file)

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
print(f"{datetime.now().strftime('%H:%M:%S')}: orders cancelled, {long_orders_left} longs left, {short_orders_left} shorts left")

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
print(f"{datetime.now().strftime('%H:%M:%S')}: ohlcv data fetched")

# --- CHECKS IF STOP LOSS WAS TRIGGERED ---
closed_orders = bitget.fetch_closed_trigger_orders(params['symbol'])
tracker_info = read_tracker_file(tracker_file)
if len(closed_orders) > 0 and closed_orders[-1]['id'] in tracker_info['stop_loss_ids']:
    update_tracker_file(tracker_file, {
        "last_side": closed_orders[-1]['info']['posSide'],
        "status": "stop_loss_triggered",
        "stop_loss_ids": [],
    })
    print(f"{datetime.now().strftime('%H:%M:%S')}: /!\\ stop loss was triggered")

# --- CHECK FOR MULTIPLE OPEN POSITIONS AND CLOSE THE EARLIEST ONE ---
positions = bitget.fetch_open_positions(params['symbol'])
if positions:
    sorted_positions = sorted(positions, key=lambda x: x['timestamp'], reverse=True)
    latest_position = sorted_positions[0]
    for pos in sorted_positions[1:]:
        bitget.flash_close_position(pos['symbol'], side=pos['side'])
        print(f"{datetime.now().strftime('%H:%M:%S')}: double position case, closing the {pos['side']}.")

# --- CHECKS IF A POSITION IS OPEN ---
position = bitget.fetch_open_positions(params['symbol'])
open_position = True if len(position) > 0 else False
if open_position:
    position = position[0]
    print(f"{datetime.now().strftime('%H:%M:%S')}: {position['side']} position of {round(position['contracts'] * position['contractSize'], 2)} ~ {round(position['contracts'] * position['contractSize'] * position['markPrice'], 2)} USDT is running")

# --- CHECKS IF CLOSE ALL SHOULD TRIGGER ---
if 'price_jump_pct' in params and open_position:
    if position['side'] == 'long':
        if data['close'].iloc[-1] < float(position['info']['openPriceAvg']) * (1 - params['price_jump_pct']):
            bitget.flash_close_position(params['symbol'])
            update_tracker_file(tracker_file, {
                "last_side": "long",
                "status": "close_all_triggered",
                "stop_loss_ids": [],
            })
            print(f"{datetime.now().strftime('%H:%M:%S')}: /!\\ close all was triggered")

    elif position['side'] == 'short':
        if data['close'].iloc[-1] > float(position['info']['openPriceAvg']) * (1 + params['price_jump_pct']):
            bitget.flash_close_position(params['symbol'])
            update_tracker_file(tracker_file, {
                "last_side": "short",
                "status": "close_all_triggered",
                "stop_loss_ids": [],
            })
            print(f"{datetime.now().strftime('%H:%M:%S')}: /!\\ close all was triggered")

# --- OK TO TRADE CHECK ---
tracker_info = read_tracker_file(tracker_file)
print(f"{datetime.now().strftime('%H:%M:%S')}: okay to trade check, status was {tracker_info['status']}")
last_price = data['close'].iloc[-1]
resume_price = data['average'].iloc[-1]
if tracker_info['status'] != "ok_to_trade":
    if ('long' == tracker_info['last_side'] and last_price >= resume_price) or (
            'short' == tracker_info['last_side'] and last_price <= resume_price):
        update_tracker_file(tracker_file, {"status": "ok_to_trade", "last_side": tracker_info['last_side']})
        print(f"{datetime.now().strftime('%H:%M:%S')}: status is now ok_to_trade")
    else:
        print(f"{datetime.now().strftime('%H:%M:%S')}: <<< status is still {tracker_info['status']}")
        sys.exit()

# --- SET POSITION MODE, MARGIN MODE, LEVERAGE ---
if not open_position:
    positions = bitget.fetch_open_positions(params['symbol'])
    if positions:
        # Close positions before changing margin mode
        print(f"{datetime.now().strftime('%H:%M:%S')}: Closing open positions before changing margin mode")
        for pos in positions:
            bitget.flash_close_position(pos['symbol'], side=pos['side'])

        # Wait for positions to close before continuing
        while len(bitget.fetch_open_positions(params['symbol'])) > 0:
            print(f"{datetime.now().strftime('%H:%M:%S')}: Waiting for positions to close...")
            time.sleep(5)

    try:
        # Set margin mode and leverage
        bitget.set_margin_mode(params['symbol'], margin_mode=params['margin_mode'])
        bitget.set_leverage(params['symbol'], margin_mode=params['margin_mode'], leverage=params['leverage'])
        print(f"{datetime.now().strftime('%H:%M:%S')}: Successfully set margin mode to {params['margin_mode']} and leverage to {params['leverage']}")
    except ccxt.ExchangeError as e:
        if "3400114" in str(e):
            print(f"{datetime.now().strftime('%H:%M:%S')}: Margin mode change failed: Liquidation risk detected.")
        else:
            raise e

            # The rest of your trading logic continues here...
