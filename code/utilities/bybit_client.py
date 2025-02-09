import ccxt
import json

#from colorama import Fore, Back, Style

class BybitClient():

    # Function to initialize the Bybit client
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

    # Function to fetch and display balances
    def get_balance(self):
        # Fetch BTC and USDT balances
        balance = self.session.fetch_balance(params={"accountType": "UNIFIED"})
        btc_balance = balance['BTC']
        usdt_balance = balance['USDT']

        # Print balances
        #print(Fore.GREEN + "BALANCE" + Style.RESET_ALL)
        #print(f"Balance BTC : {btc_balance}")
        print(f"Balance USDT: {usdt_balance}")
        print()

    def fetch_balance(self):
        return self.session.fetch_balance(params={"accountType": "UNIFIED"})
