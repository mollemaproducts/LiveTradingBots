import ccxt
#from colorama import Fore, Back, Style

class BybitClient():

    # Function to initialize the Bybit client
    def __init__(self, client_options, use_test_environment=True) -> None:
        self.session = ccxt.bybit(client_options)
        self.session.set_sandbox_mode(True)

    # Function to fetch and display balances
    def get_balance(self):
        # Fetch BTC and USDT balances
        balance = self.session.fetch_balance(params={'defaultType': 'future'})
        btc_balance = balance['BTC']
        usdt_balance = balance['USDT']

        # Print balances
        #print(Fore.GREEN + "BALANCE" + Style.RESET_ALL)
        print(f"Balance BTC : {btc_balance}")
        print(f"Balance USDT: {usdt_balance}")
        print()
