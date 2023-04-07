#!/usr/bin/env python

from collections import defaultdict
from typing import DefaultDict, Dict, Tuple
from utc_bot import UTCBot, start_bot
import math
import proto.utc_bot as pb
import betterproto
import asyncio
import re
import numpy as np

DAYS_IN_MONTH = 21
DAYS_IN_YEAR = 252
INTEREST_RATE = 0.02
NUM_FUTURES = 14
TICK_SIZE = 0.00001
FUTURE_CODES = [chr(ord('A') + i) for i in range(NUM_FUTURES)] # Suffix of monthly future code
CONTRACTS = ['SBL'] +  ['LBS' + c for c in FUTURE_CODES] + ['LLL']
ARB_THRESHOLD = 1


class Case1Bot(UTCBot):
    """
    An example bot
    """
    etf_suffix = ''
    async def create_etf(self, qty: int):
        '''
        Creates qty amount the ETF basket
        DO NOT CHANGE
        '''
        if len(self.etf_suffix) == 0:
            return pb.SwapResponse(False, "Unsure of swap")
        return await self.swap("create_etf_" + self.etf_suffix, qty)

    async def redeem_etf(self, qty: int):
        '''
        Redeems qty amount the ETF basket
        DO NOT CHANGE
        '''
        if len(self.etf_suffix) == 0:
            return pb.SwapResponse(False, "Unsure of swap")
        return await self.swap("redeem_etf_" + self.etf_suffix, qty) 
    
    async def days_to_expiry(self, asset):
        '''
        Calculates days to expiry for the future
        '''
        future = ord(asset[-1]) - ord('A')
        expiry = 21 * (future + 1)
        return self._day - expiry

    async def handle_exchange_update(self, update: pb.FeedMessage):
        '''
        Handles exchange updates
        '''
        kind, _ = betterproto.which_one_of(update, "msg")
        if kind == "trade_msg":
            asset = update.trade_msg.asset
            price = update.trade_msg.price
            qty = update.trade_msg.qty
            timestamp = update.trade_msg.timestamp
            # print(f"Trade: {asset} {price} {qty} {timestamp}")

        if kind == "fill_msg":
            order_id = update.fill_msg.order_id
            asset = update.fill_msg.asset
            price = update.fill_msg.price
            timestamp = update.fill_msg.timestamp

            # print(f"Fill: {order_id} {asset} {price} {timestamp}")
            
            
        #Competition event messages
        if kind == "generic_msg":
            msg = update.generic_msg.message
            
            # Used for API DO NOT TOUCH
            if 'trade_etf' in msg:
                self.etf_suffix = msg.split(' ')[1]
                
            # Updates current weather
            if "Weather" in update.generic_msg.message:
                msg = update.generic_msg.message
                weather = float(re.findall("\d+\.\d+", msg)[0])
                self._weather_log.append(weather)
                
            # Updates date
            if "Day" in update.generic_msg.message:
                self._day = int(re.findall("\d+", msg)[0])
                            
            # Updates positions if unknown message (probably etf swap)
            else:
                resp = await self.get_positions()
                if resp.ok:
                    self.positions = resp.positions
                    
        elif kind == "market_snapshot_msg":
            for asset in CONTRACTS:
                book = update.market_snapshot_msg.books[asset]
                try:
                    self._best_bid[asset] = float(book.bids[0].px) 
                    self._best_ask[asset] = float(book.bids[0].px)
                except:
                    print(len(book.bids))
            


    async def handle_round_started(self):
        ### Current day
        self._day = 0
        ### Best Bid in the order book
        self._best_bid: Dict[str, float] = defaultdict(
            lambda: 0
        )
        ### Best Ask in the order book
        self._best_ask: Dict[str, float] = defaultdict(
            lambda: 0
        )
        ### Order book for market making
        self.__orders: DefaultDict[str, Tuple[str, float]] = defaultdict(
            lambda: ("", 0)
        )
        ### TODO Recording fair price for each asset
        self._fair_price: DefaultDict[str, float] = defaultdict(
            lambda: ("", 0)
        )
        ### TODO spread fair price for each asset
        self._spread: DefaultDict[str, float] = defaultdict(
            lambda: ("", 0)
        )

        ### TODO order size for market making positions
        self._quantity: DefaultDict[str, int] = defaultdict(
            lambda: ("", 0)
        )
        
        ### List of weather reports
        self._weather_log = []
        
        await asyncio.sleep(.1)
        ###
        ### TODO START ASYNC FUNCTIONS HERE
        ###
        # asyncio.create_task(self.example_redeem_etf())
        asyncio.create_task(self.etf_arb())
                
        # Starts market making for each asset
        # for asset in CONTRACTS:
            # asyncio.create_task(self.make_market_asset(asset))

    # This is an example of creating and redeeming etfs
    # You can remove this in your actual bots.

    async def etf_arb(self):
        while True:
            # print(self._best_bid["LLL"])

            days_to_expiry = []
            for asset in CONTRACTS:
                days_to_expiry.append(await self.days_to_expiry(asset))
            # print(self._day)
            # print(CONTRACTS)

            days_to_expiry = days_to_expiry[1:-1]
            unexpired_futures_idx = np.argwhere(np.array(days_to_expiry) <= 0) #include ones expiring on current day
            unexpired_futures_idx = unexpired_futures_idx.reshape((-1))
            futures_ticker = np.array(CONTRACTS[1:-1])
            unexpired_futures_ticker = futures_ticker[unexpired_futures_idx]
            if len(unexpired_futures_ticker) >= 3:
                etf_nav_per_share_best_bid = 5 * self._best_bid[unexpired_futures_ticker[0]] \
                                            + 3 * self._best_bid[unexpired_futures_ticker[1]] \
                                            + 2 * self._best_bid[unexpired_futures_ticker[2]]
                etf_nav_per_share_best_ask = 5 * self._best_ask[unexpired_futures_ticker[0]] \
                                            + 3 * self._best_ask[unexpired_futures_ticker[1]] \
                                            + 2 * self._best_ask[unexpired_futures_ticker[2]]
                # print("ETF NAV per share best bid: {}".format(etf_nav_per_share_best_bid))
                # print("ETF NAV per share best ask: {}".format(etf_nav_per_share_best_ask))
                # print("ETF best bid: {}".format(self._best_bid["LLL"]))
                # print("ETF best ask: {}".format(self._best_ask["LLL"]))

                print(self.positions)
            
                all_positions = [self.positions.get(asset,0)  for asset in CONTRACTS]
                max_position = np.abs(all_positions).max()
                print(max_position)
                if max_position < 50 and self._best_bid["LLL"] - etf_nav_per_share_best_ask > ARB_THRESHOLD:
                    await self.create_etf(1)
                if max_position < 50 and self._best_ask["LLL"] - etf_nav_per_share_best_bid < -ARB_THRESHOLD:
                    await self.redeem_etf(1)
                for asset in CONTRACTS:
                    if self.positions.get(asset,0) > 0:
                        await self.place_order(asset, 0, 1, min(self.positions.get(asset,0), 100))
                    elif self.positions.get(asset,0) < 0:
                        await self.place_order(asset, 0, 0, min(-self.positions.get(asset,0), 100))



            await asyncio.sleep(0.001)

    async def example_redeem_etf(self):
        while True:
            redeem_resp = await self.redeem_etf(1)
            create_resp = await self.create_etf(5)
            await asyncio.sleep(1)


    ### Helpful ideas
    async def calculate_risk_exposure(self):
        pass
    
    async def calculate_fair_price(self, asset):
        pass
        
    async def make_market_asset(self, asset: str):
        while self._day <= DAYS_IN_YEAR:
            ## Old prices
            ub_oid, ub_price = self.__orders["underlying_bid_{}".format(asset)]
            ua_oid, ua_price = self.__orders["underlying_ask_{}".format(asset)]
            
            bid_px = self._fair_price[asset] - self._spread[asset]
            ask_px = self._fair_price[asset] + self._spread[asset]
            
            # If the underlying price moved first, adjust the ask first to avoid self-trades
            if (bid_px + ask_px) > (ua_price + ub_price):
                order = ["ask", "bid"]
            else:
                order = ["bid", "ask"]

            for d in order:
                if d == "bid":
                    order_id = ub_oid
                    order_side = pb.OrderSpecSide.BID
                    order_px = bid_px
                else:
                    order_id = ua_oid
                    order_side = pb.OrderSpecSide.ASK
                    order_px = ask_px

                r = await self.modify_order(
                        order_id = order_id,
                        asset_code = asset,
                        order_type = pb.OrderSpecType.LIMIT,
                        order_side = order_side,
                        qty = self._quantity[asset],
                        px = round_nearest(order_px, TICK_SIZE), 
                    )

                self.__orders[f"underlying_{d}_{asset}"] = (r.order_id, order_px)
                
        

def round_nearest(x, a):
    return round(round(x / a) * a, -int(math.floor(math.log10(a))))             



if __name__ == "__main__":
    start_bot(Case1Bot)
