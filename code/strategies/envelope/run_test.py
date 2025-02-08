import os
import sys
import ccxt

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from utilities.bybit_client import BybitClient

BYBIT_API_KEY = "ovZyOF03R434om5MX6"
BYBIT_API_SECRET = "Bmn9Wqn1bePh891gbpxfS5vyIW64MrXskftq"
USE_TESTNET = True  # True means your API keys were generated on testnet.bybit.com

PROFIT_PERCENTAGE = 0.05

# Setup authentication
client_options = {
    'apiKey': BYBIT_API_KEY,
    'secret': BYBIT_API_SECRET,
    "options": {"defaultType": "swap", "accountType": "UNIFIED"}  # Ensure UNIFIED is set
}

# Initialize Bybit client
bybit_client = BybitClient(client_options, USE_TESTNET)

# Show balance
bybit_client.get_balance()

balance = params['balance_fraction'] * params['leverage'] * bitget.fetch_balance()['USDT']['total']

