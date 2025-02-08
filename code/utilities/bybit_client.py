import ccxt

class BybitClient():

    def __init__(self, authentication, use_testenvironment=true) -> None
        self.session = ccxt.bybit(authentication)
        self.session.set_sandbox_mode(use_testenvironment)


