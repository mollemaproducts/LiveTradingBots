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
    TRIGGER_PRICE_DELTA = 0.005  # what I use for a 1h timeframe

    def __init__(self, broker_client, tracker_file, params):
        self.broker_client = broker_client
        self.tracker_file = tracker_file
        self.params = params

    def run(self):
        self.TRIGGER_PRICE_DELTA = 0.005  # what I use for a 1h timeframe

        # --- CLOSE OPEN LIMIT AND OPEN TRIGGER ORDERS ---
        self.close_open_orders()
        long_orders_left, short_orders_left = self.close_trigger_orders(0, 0)

        # --- FETCH OHLCV DATA, CALCULATE INDICATORS ---
        data = self.broker_client.fetch_recent_ohlcv(self.params['symbol'], self.params['timeframe'], 100).iloc[:-1]
        if 'DCM' == self.params['average_type']:
            ta_obj = ta.volatility.DonchianChannel(data['high'], data['low'], data['close'], window=self.params['average_period'])
            data['average'] = ta_obj.donchian_channel_mband()
        elif 'SMA' == self.params['average_type']:
            data['average'] = ta.trend.sma_indicator(data['close'], window=self.params['average_period'])
        elif 'EMA' == self.params['average_type']:
            data['average'] = ta.trend.ema_indicator(data['close'], window=self.params['average_period'])
        elif 'WMA' == self.params['average_type']:
            data['average'] = ta.trend.wma_indicator(data['close'], window=self.params['average_period'])
        else:
            raise ValueError(f"The average type {self.params['average_type']} is not supported")

        for i, e in enumerate(self.params['envelopes']):
            if f'band_high_{i + 1}' in data.columns:
                data[f'band_high_{i + 1}'] = data['average'] / (1 - e)
            else:
                print(f"Column 'band_high_{i + 1}' not found!")
            if f'band_low_{i + 1}' in data.columns:
                data[f'band_low_{i + 1}'] = data['average'] * (1 - e)
            else:
                print(f"Column 'band_low_{i + 1}' not found!")
            logging.info(f"{datetime.now().strftime('%H:%M:%S')}: ohlcv data fetched")

        # --- CHECKS IF STOP LOSS WAS TRIGGERED ---
        closed_orders = self.broker_client.fetch_closed_trigger_orders(self.params['symbol'])
        tracker_info = self.tracker_file.read_tracker_file()
        if len(closed_orders) > 0 and closed_orders[-1]['id'] in tracker_info['stop_loss_ids']:
            update_tracker_file(self.tracker_file, {
                "last_side": closed_orders[-1]['info']['posSide'],
                "status": "stop_loss_triggered",
                "stop_loss_ids": [],
            })
            logging.info(f"{datetime.now().strftime('%H:%M:%S')}: /!\\ stop loss was triggered")


        # --- CHECK FOR MULTIPLE OPEN POSITIONS AND CLOSE THE EARLIEST ONE ---
        positions = self.broker_client.fetch_open_positions(self.params['symbol'])
        if positions:
            sorted_positions = sorted(positions, key=lambda x: x['timestamp'], reverse=True)
            latest_position = sorted_positions[0]
            for pos in sorted_positions[1:]:
                self.broker_client.flash_close_position(pos['symbol'], side=pos['side'])
                logging.info(f"{datetime.now().strftime('%H:%M:%S')}: double position case, closing the {pos['side']}.")
                time.sleep(self.SLEEP_TIME)

        # --- CHECKS IF A POSITION IS OPEN ---
        position = self.broker_client.fetch_open_positions(self.params['symbol'])
        open_position = True if len(position) > 0 else False
        if open_position:
            position = position[0]
            logging.info(f"{datetime.now().strftime('%H:%M:%S')}: {position['side']} position of {round(position['contracts'] * position['contractSize'],2)} ~ {round(position['contracts'] * position['contractSize'] * position['markPrice'],2)} USDT is running")


        # --- CHECKS IF CLOSE ALL SHOULD TRIGGER ---
        if 'price_jump_pct' in self.params and open_position:
            if position['side'] == 'long':
                if data['close'].iloc[-1] < float(position['info']['avgPrice']) * (1 - self.params['price_jump_pct']):
                    self.broker_client.flash_close_position(self.params['symbol'])
                    update_tracker_file(self.tracker_file, {
                        "last_side": "long",
                        "status": "close_all_triggered",
                        "stop_loss_ids": [],
                    })
                    logging.info(f"{datetime.now().strftime('%H:%M:%S')}: /!\\ close all was triggered")

            elif position['side'] == 'short':
                if data['close'].iloc[-1] > float(position['info']['avgPrice']) * (1 + self.params['price_jump_pct']):
                    self.broker_client.flash_close_position(self.params['symbol'])
                    update_tracker_file(self.tracker_file, {
                        "last_side": "short",
                        "status": "close_all_triggered",
                        "stop_loss_ids": [],
                    })
                    logging.info(f"{datetime.now().strftime('%H:%M:%S')}: /!\\ close all was triggered")
            time.sleep(self.SLEEP_TIME)

        # --- OK TO TRADE CHECK ---
        tracker_info = self.tracker_file.read_tracker_file()
        logging.info(f"{datetime.now().strftime('%H:%M:%S')}: okay to trade check, status was {tracker_info['status']}")
        last_price = data['close'].iloc[-1]
        resume_price = data['average'].iloc[-1]
        if tracker_info['status'] != "ok_to_trade":
            if ('long' == tracker_info['last_side'] and last_price >= resume_price) or (
                    'short' == tracker_info['last_side'] and last_price <= resume_price):
                self.tracker_file.update_tracker_file({"status": "ok_to_trade", "last_side": tracker_info['last_side']})
                logging.info(f"{datetime.now().strftime('%H:%M:%S')}: status is now ok_to_trade")
            else:
                logging.info(f"{datetime.now().strftime('%H:%M:%S')}: <<< status is still {tracker_info['status']}")
                sys.exit()


        # --- SET POSITION MODE, MARGIN MODE, LEVERAGE ---
        if not open_position:
            time.sleep(self.SLEEP_TIME)
            self.broker_client.set_margin_mode(self.params['symbol'], margin_mode=self.params['margin_mode'])
            #logging.info(f"Attempting to set leverage for {self.params['symbol']} to {self.params['leverage']}")
            #self.broker_client.set_leverage(self.params['symbol'], margin_mode=self.params['margin_mode'], leverage=self.params['leverage'])


        # --- IF OPEN POSITION CHANGE TP AND SL ---
        if open_position:
            if position['side'] == 'long':
                close_side = 'sell'
                stop_loss_price = float(position['info']['avgPrice']) * (1 - self.params['stop_loss_pct'])
                trigger_direction = "below"
            elif position['side'] == 'short':
                close_side = 'buy'
                stop_loss_price = float(position['info']['avgPrice']) * (1 + self.params['stop_loss_pct'])
                trigger_direction = "above"

            amount = position['contracts'] * position['contractSize']

            # exit
            self.broker_client.place_trigger_market_order(
                symbol=self.params['symbol'],
                side=close_side,
                amount=amount,
                trigger_price=data['average'].iloc[-1],
                reduce=True,
                print_error=True,
            )
            # sl
            sl_order = self.broker_client.place_trigger_market_order(
                symbol=self.params['symbol'],
                side=close_side,
                amount=amount,
                trigger_price=stop_loss_price,
                reduce=True,
                print_error=True,
            )
            info = {
                "status": "ok_to_trade",
                "last_side": position['side'],
                "stop_loss_price": stop_loss_price,
                "stop_loss_ids": [sl_order['id']],
            }
            logging.info(f"{datetime.now().strftime('%H:%M:%S')}: placed close {position['side']} orders: exit price {data['average'].iloc[-1]}, sl price {stop_loss_price}")

        else:
            info = {
                "status": "ok_to_trade",
                "last_side": tracker_info['last_side'],
                "stop_loss_ids": [],
            }


        # --- FETCHING AND COMPUTING BALANCE ---
        balance = self.params['balance_fraction'] * self.params['leverage'] * self.broker_client.fetch_balance()['USDT']['total']
        logging.info(f"{datetime.now().strftime('%H:%M:%S')}: the trading balance is {balance}")

        current_balance = self.broker_client.fetch_balance()
        usdt_balance = float(current_balance['total'].get('USDT', 0)) # Ensure it's a float, default to 0 if missing
        logging.info(f"{datetime.now().strftime('%H:%M:%S')}: Current balance (USDT): {usdt_balance}")

        # --- PLACE ORDERS DEPENDING ON HOW MANY BANDS HAVE ALREADY BEEN HIT ---
        if open_position:
            long_ok = True if 'long' == position['side'] else False
            short_ok = True if 'short' == position['side'] else False
            range_longs = range(len(self.params['envelopes']) - long_orders_left, len(self.params['envelopes']))
            range_shorts = range(len(self.params['envelopes']) - short_orders_left, len(self.params['envelopes']))
        else:
            long_ok = True
            short_ok = True
            range_longs = range(len(self.params['envelopes']))
            range_shorts = range(len(self.params['envelopes']))

        if not self.params['use_longs']:
            long_ok = False

        if not self.params['use_shorts']:
            short_ok = False

        if long_ok:
            for i in range_longs:
                entry_limit_price = data[f'band_low_{i + 1}'].iloc[-1]
                entry_trigger_price = (1 + self.TRIGGER_PRICE_DELTA) * entry_limit_price
                amount = balance / len(self.params['envelopes']) / entry_limit_price
                min_amount = self.broker_client.fetch_min_amount_tradable(self.params['symbol'])
                if amount >= min_amount:
                    # entry
                    self.broker_client.place_trigger_limit_order(
                        symbol=self.params['symbol'],
                        side='buy',
                        amount=amount,
                        trigger_price=entry_trigger_price,
                        price=entry_limit_price,
                        print_error=True,
                    )
                    logging.info(f"{datetime.now().strftime('%H:%M:%S')}: placed open long trigger limit order of {amount}, trigger price {entry_trigger_price}, price {entry_limit_price}")
                    # exit
                    self.broker_client.place_trigger_market_order(
                        symbol=self.params['symbol'],
                        side='sell',
                        amount=amount,
                        trigger_price=data['average'].iloc[-1],
                        reduce=True,
                        print_error=True,
                    )
                    print(f"{datetime.now().strftime('%H:%M:%S')}: placed exit long trigger market order of {amount}, price {data['average'].iloc[-1]}")
                    # sl
                    sl_order = self.broker_client.place_trigger_market_order(
                        symbol=self.params['symbol'],
                        side='sell',
                        amount=amount,
                        trigger_price=data[f'band_low_{i + 1}'].iloc[-1] * (1 - self.params['stop_loss_pct']),
                        reduce=True,
                        print_error=True,
                    )
                    if sl_order:
                        info["stop_loss_ids"].append(sl_order['id'])
                        logging.info(f"{datetime.now().strftime('%H:%M:%S')}: placed sl long trigger market order of {amount}, price {data[f'band_low_{i + 1}'].iloc[-1] * (1 - self.params['stop_loss_pct'])}")
                    else:
                        if isinstance(position, list) and len(position) > 0:
                            position = position[0]  # Ensure we reference the first position
                            logging.info(f"{datetime.now().strftime('%H:%M:%S')}: /!\\ Failed to place stop loss order for {position.get('side', 'unknown')} position.")
                else:
                    logging.info(f"{datetime.now().strftime('%H:%M:%S')}: /!\\ long orders not placed for envelope {i+1}, amount {amount} smaller than minimum requirement {min_amount}")

        if short_ok:
            for i in range_shorts:
                entry_limit_price = data[f'band_high_{i + 1}'].iloc[-1]
                entry_trigger_price = (1 - self.TRIGGER_PRICE_DELTA) * entry_limit_price
                amount = balance / len(self.params['envelopes']) / entry_limit_price
                min_amount = self.broker_client.fetch_min_amount_tradable(self.params['symbol'])
                if amount >= min_amount:
                    # entry
                    self.broker_client.place_trigger_limit_order(
                        symbol=self.params['symbol'],
                        side='sell',
                        amount=amount,
                        trigger_price= entry_trigger_price,
                        price=entry_limit_price,
                        print_error=True,
                    )
                    logging.info(f"{datetime.now().strftime('%H:%M:%S')}: placed open short trigger limit order of {amount}, trigger price {entry_trigger_price}, price {entry_limit_price}")
                    # exit
                    self.broker_client.place_trigger_market_order(
                        symbol=self.params['symbol'],
                        side='buy',
                        amount=amount,
                        trigger_price=data['average'].iloc[-1],
                        reduce=True,
                        print_error=True,
                    )
                    logging.info(f"{datetime.now().strftime('%H:%M:%S')}: placed exit short trigger market order of {amount}, price {data['average'].iloc[-1]}")
                    # sl
                    sl_order = self.broker_client.place_trigger_market_order(
                        symbol=self.params['symbol'],
                        side='buy',
                        amount=amount,
                        trigger_price=data[f'band_high_{i + 1}'].iloc[-1] * (1 + self.params['stop_loss_pct']),
                        reduce=True,
                        print_error=True,
                    )
                    if sl_order:
                        info["stop_loss_ids"].append(sl_order['id'])
                        logging.info(f"{datetime.now().strftime('%H:%M:%S')}: placed sl short trigger market order of {amount}, price {data[f'band_high_{i + 1}'].iloc[-1] * (1 - self.params['stop_loss_pct'])}")
                    else:
                        if isinstance(position, list) and len(position) > 0:
                            position = position[0]  # Ensure we reference the first position
                            logging.info(f"{datetime.now().strftime('%H:%M:%S')}: /!\\ Failed to place stop loss order for {position.get('side', 'unknown')} position.")
                else:
                    logging.info(f"{datetime.now().strftime('%H:%M:%S')}: /!\\ short orders not placed for envelope {i+1}, amount {amount} smaller than minimum requirement {min_amount}")

        self.tracker_file.update_tracker_file(info)
        logging.info(f"{datetime.now().strftime('%H:%M:%S')}: <<< all done")

    def close_trigger_orders(self, long_orders_left, short_orders_left):
        trigger_orders = self.broker_client.fetch_open_trigger_orders(self.params['symbol'])
        if trigger_orders :
            for order in trigger_orders:
                if order['side'] == 'buy' and order['info']['tradeSide'] == 'open':
                    long_orders_left += 1
                elif order['side'] == 'sell' and order['info']['tradeSide'] == 'open':
                    short_orders_left += 1
                self.broker_client.cancel_trigger_order(order['id'], self.params['symbol'])
                logging.info(
                    f"{datetime.now().strftime('%H:%M:%S')}: orders cancelled, {long_orders_left} longs left, {short_orders_left} shorts left")
        return long_orders_left, short_orders_left

    def close_open_orders(self):
        orders = self.broker_client.fetch_open_orders(self.params['symbol'])
        for order in orders:
            self.broker_client.cancel_order(order['id'], self.params['symbol'])