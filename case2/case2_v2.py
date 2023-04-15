#!/usr/bin/env python

from utc_bot import UTCBot, start_bot
import proto.utc_bot as pb
import numpy as np
import pandas as pd
import betterproto
from py_vollib.black_scholes.greeks.numerical import delta
from py_vollib.black_scholes.greeks.numerical import gamma
from py_vollib.black_scholes.greeks.numerical import theta
from py_vollib.black_scholes.greeks.numerical import vega
from py_vollib.black_scholes import black_scholes as bs
import asyncio
import json

PARAM_FILE = "params.json"
RUN_DURATION = 0.25 - (0.25/3.0)
PERIOD_DURATION = RUN_DURATION/600
flags = ["C", "P"]
greeks = ["D", "T", "G", "V"]
option_strikes = np.arange(65, 140, 5)

class OptionBot(UTCBot):
    """
    An example bot that reads from a file to set internal parameters during the round
    """
    prices_df = pd.read_csv("../data/case2/training_pricepaths.csv")
    prices_df.rename(columns={"underlying": "SPY", "call65": "SPY65C", "call70": "SPY70C", "call75": "SPY75C", "call80": "SPY80C"
                       , "call85": "SPY85C", "call90": "SPY90C", "call95": "SPY95C"
                       , "call100": "SPY100C", "call105": "SPY105C", "call110": "SPY110C", "call115": "SPY115C"
                       , "call120": "SPY120C", "call125": "SPY125C", "call130": "SPY130C", "call135": "SPY135C"})

    returns = prices_df / prices_df.shift(0) - 1
    ticks_elapsed = 0

    async def handle_round_started(self):
        self.books = {}
        self.positions = {}
        self.price_path = self.prices_df
        self.cur_prices = {}
        self.ticks_elapsed = 0
        self.cur_greeks = {}

        self.cur_greeks["SPY"] = 0
        self.positions["SPY"] = 0
        self.cur_prices["SPY"] = 100
        for strike in option_strikes:
            for flag in flags:
                self.positions[f"SPY{strike}{flag}"] = 0
                self.cur_prices[f"SPY{strike}{flag}"] = 0

        self.greek_limits = {
            "delta": 2000,
            "gamma": 50000,
            "theta": 5000,
            "vega": 1000000
        }
        self.my_greek_limits = {
            "delta": 0,
            "gamma": 0,
            "theta": 0,
            "vega": 0
        }

    async def handle_exchange_update(self, update: pb.FeedMessage):
        kind, _ = betterproto.which_one_of(update, "msg")

        if kind == "pnl_msg":
            # When you hear from the exchange about your PnL, print it out
            #print("My PnL:", update.pnl_msg.m2m_pnl)
            #print(f"Positions: {self.positions}")
            #print(f"Greeks: {self.my_greek_limits}")
            print("pnl")

        elif kind == "fill_msg":
            # When you hear about a fill you had, update your positions
            fill_msg = update.fill_msg

            if fill_msg.order_side == pb.FillMessageSide.BUY:
                self.positions[fill_msg.asset] += update.fill_msg.filled_qty
            else:
                self.positions[fill_msg.asset] -= update.fill_msg.filled_qty

        elif kind == "market_snapshot_msg":
            for strike in option_strikes:
                for flag in flags:
                    self.books[f"SPY{strike}{flag}"] = update.market_snapshot_msg.books[f"SPY{strike}{flag}"]
            book = update.market_snapshot_msg.books["SPY"]

            # Compute the mid-price of the market and store it
            if len(book.bids) > 0 and len(book.asks) > 0:
                self.cur_prices["SPY"] = (float(book.bids[0].px) + float(book.asks[0].px)) / 2
                for flag in flags:
                    for strike in option_strikes:
                        if len(self.books[f"SPY{strike}{flag}"].bids) > 0 and len(self.books[f"SPY{strike}{flag}"].asks) > 0:
                            self.cur_prices[f"SPY{strike}{flag}"] = (float(self.books[f"SPY{strike}{flag}"].bids[0].px)\
                                                                    + float(self.books[f"SPY{strike}{flag}"].bids[0].px)) / 2
            self.price_path = pd.concat([self.price_path, pd.DataFrame(self.cur_prices, index=[0])])
            self.update_greek_limits()
            await self.add_trade(self.compute_vol_estimate())

    async def add_trade(self, vol):
        requests = []
        proposed_prices = {}
        for strike in option_strikes:
            for flag in flags:
                proposed_prices[f"SPY{strike}{flag}"] = bs(flag.lower(), self.cur_prices["SPY"], strike, self.time_to_maturity(), 0.00, vol[f"SPY{strike}{flag}"])
        for strike in option_strikes:
            for flag in flags:
                asset = f'SPY{strike}{flag}'
                print(f"Gonna try to buy {asset}")
                if (asset in self.books):
                    book = self.books[asset]
                    for ask in book.asks:
                        if float(ask.px) < proposed_prices[asset] and flag == "P":
                                if self.under_greek_threshold(strike, flag.lower(), self.cur_prices["SPY"], self.time_to_maturity(), vol[f"SPY{strike}{flag}"]):
                                    print(f"Appending: {asset} at {proposed_prices[asset] * 1.5}")
                                    requests.append(
                                        await self.place_order(
                                            asset,
                                            pb.OrderSpecType.LIMIT,
                                            pb.OrderSpecSide.BID,
                                            1,  # How should this quantity be chosen?
                                            float(ask.px)  # How should this price be chosen?
                                        )
                                    )
                    for bid in book.bids:
                        if float(bid.px) < proposed_prices[asset] and flag == "C":
                            if self.under_greek_threshold(strike, flag.lower(), self.cur_prices["SPY"], self.time_to_maturity(), vol[f"SPY{strike}{flag}"]):
                                print(f"Appending: {asset} at {proposed_prices[asset] * 1.5}")
                                requests.append(
                                    await self.place_order(
                                        asset,
                                        pb.OrderSpecType.LIMIT,
                                        pb.OrderSpecSide.ASK,
                                        1,  # How should this quantity be chosen?
                                        float(bid.px)  # How should this price be chosen?
                                    )
                                )

    def time_to_maturity(self): #Evaluates time to maturity
        return 0.25 - self.ticks_elapsed * PERIOD_DURATION

    def compute_vol_estimate(self):
        vol_surf = self.price_path.std()

        volatility = vol_surf * (252 ** 0.5)
        return volatility
    def update_greek_limits(self):
        # add to our greek limits
        vol = self.compute_vol_estimate()
        time_to_expiry = self.time_to_maturity()
        for strike in option_strikes:
            for flag in flags:
                count = self.positions[f"SPY{strike}{flag}"]
                flagL = flag.lower()
                self.my_greek_limits["delta"] = delta(flagL, self.cur_prices["SPY"], strike, time_to_expiry, 0.0, vol[f"SPY{strike}{flag}"]) * count
                self.my_greek_limits["gamma"] = gamma(flagL, self.cur_prices["SPY"], strike, time_to_expiry, 0.0, vol[f"SPY{strike}{flag}"]) * count
                self.my_greek_limits["theta"] = theta(flagL, self.cur_prices["SPY"], strike, time_to_expiry, 0.0, vol[f"SPY{strike}{flag}"]) * count
                self.my_greek_limits["vega"] = vega(flagL, self.cur_prices["SPY"], strike, time_to_expiry, 0.0, vol[f"SPY{strike}{flag}"]) * count

    def determine_volume(self, strike, flag, underlying_price, time_to_expiry, vol):
        delta1 = delta(flag, underlying_price, strike, time_to_expiry, 0.00, vol)
        gamma1 = gamma(flag, underlying_price, strike, time_to_expiry, 0.00, vol)
        theta1 = theta(flag, underlying_price, strike, time_to_expiry, 0.00, vol)
        vega1 = vega(flag, underlying_price, strike, time_to_expiry, 0.00, vol)

    def under_greek_threshold(self, strike, flag, underlying_price, time_to_expiry, vol):
        print(f"Greeks: {self.my_greek_limits}")
        cur_delta = self.my_greek_limits["delta"]
        if cur_delta + delta(flag, underlying_price, strike, time_to_expiry, 0.00, vol) > self.greek_limits["delta"]:
            print(
                f"Breaking Delta: {cur_delta + delta(flag, underlying_price, strike, time_to_expiry, 0.00, vol)} > 2000")
            return False
        cur_gamma = self.my_greek_limits["gamma"]
        if cur_gamma + gamma(flag, underlying_price, strike, time_to_expiry, 0.00, vol) > self.greek_limits["gamma"]:
            print(f"Breaking Gamma: {cur_gamma + gamma(flag, underlying_price, strike, time_to_expiry, 0.00, vol)}")
            return False
        cur_theta = self.my_greek_limits["theta"]
        if cur_theta + theta(flag, underlying_price, strike, time_to_expiry, 0.00, vol) > self.greek_limits["theta"]:
            print(f"Breaking Theta: {cur_theta + theta(flag, underlying_price, strike, time_to_expiry, 0.00, vol)}")
            return False
        cur_vega = self.my_greek_limits["vega"]
        if cur_vega + vega(flag, underlying_price, strike, time_to_expiry, 0.00, vol) > self.greek_limits["vega"]:
            print(f"Breaking Vega: {cur_vega + vega(flag, underlying_price, strike, time_to_expiry, 0.00, vol)}")
            return False
        # nothing failed so the order will be placed
        return True

if __name__ == "__main__":
    start_bot(OptionBot)
