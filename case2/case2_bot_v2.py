from dataclasses import astuple
from datetime import datetime
from utc_bot import UTCBot, start_bot
from py_vollib.black_scholes import black_scholes as bs
import proto.utc_bot as pb
import betterproto
import numpy as np
import asyncio
import matplotlib.pyplot as plt
from py_vollib.black_scholes.greeks.analytical import delta
from py_vollib.black_scholes.greeks.analytical import gamma
from py_vollib.black_scholes.greeks.analytical import theta
from py_vollib.black_scholes.greeks.analytical import vega
from py_vollib.black_scholes.greeks.analytical import rho

option_strikes = [65,70,75,80,85,90,95,100,105,110,115,120,125,130,135]


class Case2(UTCBot):

    async def handle_starting_round(self):
        
        self.positions = {}

        self.positions["SPY"] = 0

        for strike in option_strikes:
            for flag in ["C", "P"]:
                self.positions[f"SPY{strike}{flag}"] = 0
        
        self.run_duration = 0.25 - (0.25/3.0)
        self.period_duration = self.run_duration/600

        self.starting_time_to_maturity = 0.25

        self.number_updates = 0


        self.pnl = 0.0
        self.price_path = []
        self.volatilities = []

        self.greek_lims = {
            "delta": 2000,
            "gamma": 5000,
            "theta": 5000,
            "vega": 1000000
        }

        self.greek_perso_lims =  {
            "delta": 0,
            "gamma": 0,
            "theta": 0,
            "vega": 0
        }

        self.books = {}
        self.safe_buy = 0


    def pricer (self, flag: str, S: float, K: float, t: float, r: float, sigma: float):
        price = 0
        if (flag == "c" or flag == "C"):
            price = bs('c', S, K, t, 0.00, sigma)
        elif (flag == "p" or flag == "P"):
            price = bs('p', S, K, t, 0.00, sigma)
        
        return np.round(price, 1)
    
    def calibrate_volatility(self, flag, S, K, periods, r, sigma):
        self.implied_vol = 0.176
        self.realized_vol = 0.000
        self.ri_table = {}
        for i in self.price_path:
            self.ri = (self.price_path[i+1] -self.price_path[i])
            self.ri_table.append(self.ri)
            self.sum = self.sum + self.ri
        self.mean_price_returns = self.sum/len(self.price_path)

        for i in self.ri_table:
            self.sub_squared = (self.ri_table[i] - self.mean_price_returns)**2
            self.sum_2 = self.sum_2 + self.sub_squared

        self.realized_vol = np.sqrt(self.sum_2/len(self.price_path-1))
        
        if(len(self.price_path == 1)):
            return 0.176
        elif(len)
        
        
    

