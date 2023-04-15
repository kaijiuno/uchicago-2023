#!/usr/bin/env python

from utc_bot import UTCBot, start_bot
import proto.utc_bot as pb
import numpy as np
import pandas as pd
import betterproto
from py_vollib.black_scholes.greeks.analytical import delta
from py_vollib.black_scholes.greeks.analytical import gamma
from py_vollib.black_scholes.greeks.analytical import theta
from py_vollib.black_scholes.greeks.analytical import vega
from py_vollib.black_scholes.greeks.analytical import rho
import asyncio
import json

PARAM_FILE = "params.json"
RUN_DURATION = 0.25 - (0.25/3.0)
PERIOD_DURATION = RUN_DURATION/600
flags = ["C", "P"]
option_strikes = np.arange(65, 140, 5)

class OptionBot(UTCBot):
    """
    An example bot that reads from a file to set internal parameters during the round
    """
    df = pd.read_csv("../data/case2/training_pricepaths.csv")

    returns = df / df.shift(0) - 1
    ticks_elapsed = 0

    async def handle_round_started(self):
        self.books = {}
        self.positions = {}
        self.price_path = {}

        self.positions["SPY"] = 0
        for strike in option_strikes:
            for flag in flags:
                self.positions[f"SPY{strike}{flag}"] = 0

        self.greek_limits = {
            "delta": 2000,
            "gamma": 5000,
            "theta": 50000,
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
            print("My PnL:", update.pnl_msg.m2m_pnl)
            print(f"Positions: {self.positions}")

        elif kind == "fill_msg":
            # When you hear about a fill you had, update your positions
            fill_msg = update.fill_msg

            if fill_msg.order_side == pb.FillMessageSide.BUY:
                self.positions[fill_msg.asset] += update.fill_msg.filled_qty
            else:
                self.positions[fill_msg.asset] -= update.fill_msg.filled_qty

        elif kind == "market_snapshot_msg":
            self.ticks_elapsed += 1

            for strike in option_strikes:
                for flag in flags:
                    self.books[f"SPY{strike}{flag}"] = update.market_snapshot_msg.books[f"SPY{strike}{flag}"]
            book = update.market_snapshot_msg.books["SPY"]

            # Compute the mid price of the market and store it
            if (len(book.bids) > 0):
                self.underlying_price = ( float(book.bids[0].px) + float(book.asks[0].px)) / 2

            self.update_greek_limits()
            # print(self.positions)

    def time_to_maturity(self): #Evaluates time to maturity
        return 0.25 - self.ticks_elapsed * PERIOD_DURATION

    def compute_vol_estimate(self) -> float:
        """
        This function is used to provide an estimate of underlying's volatility. Because this is
        an example bot, we just use a placeholder value here. We recommend that you look into
        different ways of finding what the true volatility of the underlying is.
        """

        stdev = np.std(self.price_path[-100:])

        # volatility = 0.9* np.log(stdev/2.5 + 0.375) + 0.9
        volatility = (stdev + 0.1) ** (1 / 3) - 0.5
        return volatility
    def update_greek_limits(self):
        # add to our greek limits
        vol = self.compute_vol_estimate()
        time_to_expiry = self.time_to_maturity()
        for strike in option_strikes:
            for flag in flags:
                count = self.positions[f"SPY{strike}{flag.upper()}"]
                self.greek_limits["delta"] = delta(flag, self.underlying_price, strike, time_to_expiry, vol) * count
                self.greek_limits["gamma"] = gamma(flag, self.underlying_price, strike, time_to_expiry, vol) * count
                self.greek_limits["theta"] = theta(flag, self.underlying_price, strike, time_to_expiry, vol) * count
                self.greek_limits["vega"] = vega(flag, self.underlying_price, strike, time_to_expiry, vol) * count

    def evaluate_greeks(self, strike, flag, underlying_price, time_to_expiry, vol):
        cur_delta = self.my_greek_limits["delta"]
        if cur_delta + delta(underlying_price, strike, vol, time_to_expiry, 0.00, flag) > self.greek_limits["delta"]:
            print(
                f"Breaking Delta: {cur_delta + delta(underlying_price, strike, vol, time_to_expiry, 0.00, flag)} > 2000")
            return False
        cur_gamma = self.my_greek_limits["gamma"]
        if cur_gamma + gamma(underlying_price, strike, vol, time_to_expiry, 0.00, flag) > self.greek_limits["gamma"]:
            print(f"Breaking Gamma: {cur_gamma + gamma(underlying_price, strike, vol, time_to_expiry, 0.00, flag)}")
            return False
        cur_theta = self.my_greek_limits["theta"]
        if cur_theta + theta(underlying_price, strike, vol, time_to_expiry, 0.00, flag) > self.greek_limits["theta"]:
            print(f"Breaking Theta: {cur_theta + theta(underlying_price, strike, vol, time_to_expiry, 0.00, flag)}")
            return False
        cur_vega = self.my_greek_limits["vega"]
        if cur_vega + vega(underlying_price, strike, vol, time_to_expiry, 0.00, flag) > self.greek_limits["vega"]:
            print(f"Breaking Vega: {cur_vega + vega(underlying_price, strike, vol, time_to_expiry, 0.00, flag)}")
            return False
        # nothing failed so the order will be placed
        return True

if __name__ == "__main__":
    start_bot(OptionBot)
