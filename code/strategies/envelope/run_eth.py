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
from logger_config import Logger
from tracker_file import TrackerFile
from strategy_logic_old import StrategyLogic

# Basic configuration
coin = "ETH"
sympol = coin + "/USDT:USDT"
balance_fraction = 0.3

# Initialize
Logger.init(config.PATH_LOGGING, coin)
tracker_file = TrackerFile(config.PATH_TRACKER_FILE, sympol)
path_secret_json = os.path.join(config.PATH_PROJECT_ROOT, "secret.json")
broker_client = BybitClient(path_secret_json, "bybit_demo")

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

StrategyLogic(broker_client, tracker_file, params).run()