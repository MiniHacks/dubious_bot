import logging
from math import sqrt
import statistics
import time
from optibook import ORDER_TYPE_LIMIT, SIDE_ASK, SIDE_BID
from optibook.exchange_responses import InsertOrderResponse
from optibook.synchronous_client import Exchange
from collections import defaultdict
from functools import reduce
import colors
from helper import color_pm_float, color_pm_int

LEVEL = 0.1
OWN_WEIGHT = 0.03
OTHER_INSIDE_WEIGHT = 0.001
OTHER_OUTSIDE_WEIGHT = 0.0003

root = logging.getLogger()
if root.handlers:
    for handler in root.handlers:
        root.removeHandler(handler)

logging.basicConfig(
    datefmt="%H:%M:%S",
    format=f"{colors.GREY}%(asctime)s.%(msecs)03d{colors.END} %(message)s",
    level=logging.DEBUG,
)


class TradingAlgorithm:
    def __init__(self, exchange):
        self.exchange = exchange
        self.prev_pnl = self.pnl = self.exchange.get_pnl()
        self.instruments = ["SMALL_CHIPS_NEW_COUNTRY", "SMALL_CHIPS"]
        self.is_trading = defaultdict(bool)
        self.own_trades = defaultdict(list)
        self.market_trades = defaultdict(list)
        self.deltas = 0

        self.n = 0
        self.sample_mean = 0
        self.sample_stdev = 0
        self.square_sum = 0
        self.sum = 0

        while not (tradable_instruments := self.exchange.get_instruments()):
            time.sleep(0.2)
        for instrument_id in self.instruments:
            if instrument_id not in tradable_instruments:
                raise Exception(
                    f"'{instrument_id}' does not exist. Options: {tradable_instruments}"
                )

        self.book = defaultdict(list)
        for instrument_id in self.instruments:
            self.book[instrument_id] = self.exchange.get_last_price_book(instrument_id)

        self.theo, self.margin = self.compute_market_book()
        self.volume_curve = [2, 8, 16, 32]

    def place_order(self, instrument_id, price, volume, side):
        bid_response: InsertOrderResponse = self.exchange.insert_order(
            instrument_id,
            price=price,
            side=(SIDE_BID if side == "bid" else SIDE_ASK),
            volume=volume,
            order_type=ORDER_TYPE_LIMIT,  # add fill-kill
        )
        if not bid_response.success:
            logging.info(
                f"{colors.RED} Unable to insert order: {bid_response.success}{colors.END}"
            )

    def place_quotes_levels(self, instrument_id, initial_level, side):
        for steps, level_volume in enumerate(self.volume_curve):
            self.place_order(
                instrument_id,
                initial_level + LEVEL * steps * (1 if side == "ask" else -1),
                level_volume,
                side,
            )

    def compute_market_book(self):
        while (
            not self.book["SMALL_CHIPS"]
            or not self.book["SMALL_CHIPS"].asks
            or not self.book["SMALL_CHIPS"].bids
        ):
            logging.info(f"{colors.YELLOW2}Waiting for SMALL_CHIPS book.{colors.END}")
            time.sleep(1)
            self.book["SMALL_CHIPS"] = self.exchange.get_last_price_book("SMALL_CHIPS")
        logging.info(
            f"{colors.YELLOW2}Computing initial market from SMALL_CHIPS book.{colors.END}"
        )
        book = self.book["SMALL_CHIPS"]
        ask = book.asks[0]
        bid = book.bids[0]

        theo = (ask.price * ask.volume + bid.price * bid.volume) / (
            bid.volume + ask.volume
        )
        margin = (ask.price - bid.price) / 2
        logging.info(
            f"{colors.YELLOW2}Initial conditions set: {colors.END}{colors.VIOLET2}theo: {theo:.2f}, margin: {margin:.2f}{colors.END}"
        )

        return theo, margin

    def compute_market_ema(self):
        alpha = 0.03

        def ema_aggregate(acc, el):
            discount = (1 - alpha) ** el.volume
            return discount * acc + (1 - discount) * el.price

        ticks = self.exchange.get_trade_tick_history(
            "SMALL_CHIPS"
        ) + self.exchange.get_trade_tick_history("SMALL_CHIPS_NEW_COUNTRY")

        ticks.sort(key=lambda x: x.timestamp)
        prices = list(map(lambda x: x.price, ticks))
        mean, stdev = statistics.mean(prices), statistics.stdev(prices)
        exemplars = list(filter(lambda x: abs(mean - x.price) <= 2 * stdev, ticks))

        theo = reduce(ema_aggregate, exemplars, exemplars[0].price)
        # TODO: tweak multiplier
        margin = stdev
        return theo, margin

    def print_status(self):

        own_trades = (
            self.own_trades["SMALL_CHIPS"] + self.own_trades["SMALL_CHIPS_NEW_COUNTRY"]
        )
        market_trades = (
            self.market_trades["SMALL_CHIPS"]
            + self.market_trades["SMALL_CHIPS_NEW_COUNTRY"]
        )

        for instrument_id in self.instruments:
            if self.book[instrument_id].asks and self.book[instrument_id].bids:
                logging.info(
                    f"{instrument_id}: bid={self.book[instrument_id].bids[0].price:.2f}, ask={self.book[instrument_id].asks[0].price:.2f}, spread={(self.book[instrument_id].asks[0].price - self.book[instrument_id].bids[0].price):.2f}"
                )
            else:
                logging.info(
                    f"{instrument_id}: {self.book[instrument_id].asks} {self.book[instrument_id].bids}"
                )
            logging.info(f"{self.book[instrument_id]}")
        logging.info(
            f"{colors.WHITE2}PNL: {self.prev_pnl:.2f} -> {self.pnl:.2f}{colors.END}, (Δ: {color_pm_float(self.pnl - self.prev_pnl)}) \
            {colors.WHITE2}{len(own_trades)}/{len(market_trades)}{colors.END} trades"
        )
        logging.info(
            f"SMALL: {color_pm_int(self.positions['SMALL_CHIPS'])} {color_pm_int(self.positions['SMALL_CHIPS_NEW_COUNTRY'])}, δ: {color_pm_int(self.deltas)}"  # \
            # TECH: {color_pm_int(positions['TECH_INC'])} {color_pm_int(positions['TECH_INC_NEW_COUNTRY'])}, δ: {color_pm_int(positions['TECH_INC'] + positions['TECH_INC_NEW_COUNTRY'])}"
        )
        logging.info(own_trades)

    def update_market_state(self):
        self.positions = self.exchange.get_positions()
        self.prev_pnl, self.pnl = self.pnl, self.exchange.get_pnl()

        tradable_instruments = self.exchange.get_instruments()
        for instrument_id in self.instruments:
            self.book[instrument_id] = self.exchange.get_last_price_book(instrument_id)
            self.is_trading[instrument_id] = (
                instrument_id in tradable_instruments
                and not tradable_instruments[instrument_id].paused
            )

            self.own_trades[instrument_id] = self.exchange.poll_new_trades(
                instrument_id
            )
            self.market_trades[instrument_id] = self.exchange.poll_new_trade_ticks(
                instrument_id
            )

    def update_internal_state(self):
        own_trades = (
            self.own_trades["SMALL_CHIPS"] + self.own_trades["SMALL_CHIPS_NEW_COUNTRY"]
        )
        own_ids = set(map(lambda x: x.trade_id, own_trades))
        for trade in own_trades:
            left, right = self.theo - self.margin, self.theo + self.margin
            if left < trade.price:
                update = OWN_WEIGHT * (right - trade.price) * trade.volume
                self.theo -= update / 2
            else:
                update = OWN_WEIGHT * (trade.price - left) * trade.volume
                self.theo += update / 2
            self.margin += update / 2

            print(f"Inside, ours: {update / 2}, {update / 2}")

        market_trades = (
            self.market_trades["SMALL_CHIPS"]
            + self.market_trades["SMALL_CHIPS_NEW_COUNTRY"]
        )
        market_trades = filter(lambda x: x.trade_id not in own_ids, market_trades)
        for trade in market_trades:
            left, right = self.theo - self.margin, self.theo + self.margin
            if left > trade.price or right < trade.price:
                update = (
                    OTHER_OUTSIDE_WEIGHT
                    * (2 * trade.price - left - right)
                    * trade.volume
                )
                self.theo += update

                print(f"Outside, other: {update / 2}, {0}")

            else:
                d1 = OTHER_INSIDE_WEIGHT * (trade.price - left) * trade.volume
                d2 = OTHER_INSIDE_WEIGHT * (trade.price - right) * trade.volume

                self.margin -= (d1 - d2) / 2
                self.theo += (d1 + d2) / 2

                print(-(d1 - d2) / 2, (d1 + d2) / 2)
                print(f"Inside, other: {-(d1 - d2) / 2}, {(d1 + d2) / 2}")

        self.margin = max(self.margin, 0.05)
        self.deltas = (
            self.positions["SMALL_CHIPS"] + self.positions["SMALL_CHIPS_NEW_COUNTRY"]
        )

        prices = map(lambda x: x.price, self.market_trades["SMALL_CHIPS"])
        for price in prices:
            self.sample_mean = (
                ((self.n - 1) * self.sample_mean + price) / self.n
                if self.n > 0
                else price
            )
            self.n += 1
            self.square_sum += price * price
            self.sum += price
            self.sample_stdev = (
                1 / self.n * sqrt(self.n * self.square_sum - self.sum**2)
            )

    def propagate_trade(self, trade, theo_update_rate, margin_update_rate):
        update = trade.volume * (trade.price - self.theo)

        self.theo += theo_update_rate * update
        self.margin += margin_update_rate * abs(update)  # TODO: fix

    def send_orders(self):

        # this will be removed eventually
        for instrument_id in self.instruments:
            self.exchange.delete_orders(instrument_id)

        if self.is_trading["SMALL_CHIPS_NEW_COUNTRY"]:
            bids = self.book["SMALL_CHIPS_NEW_COUNTRY"].bids
            asks = self.book["SMALL_CHIPS_NEW_COUNTRY"].asks

            edge_bid, edge_ask = (
                bids[0].price if bids else 0,
                asks[0].price if asks else 1e7,
            )

            start_bid = min(edge_bid + 0.1, round(self.theo - self.margin - 0.05, 1))
            start_ask = max(edge_ask - 0.1, round(self.theo + self.margin + 0.05, 1))
            logging.info(
                f"{colors.VIOLET2}{self.theo:.2f}±{self.margin:.2f}: {start_bid:.2f} @ {start_ask:.2f}{colors.END}"
            )

            self.place_quotes_levels("SMALL_CHIPS_NEW_COUNTRY", start_bid, "bid")
            self.place_quotes_levels("SMALL_CHIPS_NEW_COUNTRY", start_ask, "ask")

        if self.is_trading["SMALL_CHIPS"] and self.n >= 20 and self.sample_stdev != 0:
            bids = self.book["SMALL_CHIPS"].bids
            asks = self.book["SMALL_CHIPS"].asks

            edge_bid, edge_ask = (
                bids[0].price if bids else 0,
                asks[0].price if asks else 1e7,
            )

            if (
                -(edge_ask - self.sample_mean) / self.sample_stdev > 2
                and self.deltas < 0
            ):
                logging.info(
                    f"{colors.GREEN}Lifting {-self.deltas} @ {(self.sample_mean - 2 * self.sample_stdev):.2f} {colors.END}"
                )
                self.place_order(
                    "SMALL_CHIPS",
                    self.sample_mean - 2 * self.sample_stdev,
                    -self.deltas,
                    "bid",
                )
            elif (
                -(edge_ask - self.sample_mean) / self.sample_stdev > 1.5
                and self.deltas < 0
            ):
                logging.info(
                    f"{colors.GREEN}Lifting {-min(10,self.deltas)} @ {(self.sample_mean - 1.5 * self.sample_stdev):.2f} {colors.END}"
                )
                self.place_order(
                    "SMALL_CHIPS",
                    self.sample_mean - 1.5 * self.sample_stdev,
                    min(10, -self.deltas),
                    "bid",
                )
            elif (
                self.sample_mean - edge_bid
            ) / self.sample_stdev > 2 and self.deltas > 0:
                logging.info(
                    f"{colors.GREEN}Hitting {self.deltas} @ {(self.sample_mean + 2 * self.sample_stdev):.2f} {colors.END}"
                )
                self.place_order(
                    "SMALL_CHIPS",
                    self.sample_mean + 2 * self.sample_stdev,
                    self.deltas,
                    "sell",
                )
            elif (
                self.sample_mean - edge_bid
            ) / self.sample_stdev > 1.5 and self.deltas > 0:
                logging.info(
                    f"{colors.GREEN}Hitting {min(10,self.deltas)} @ {(self.sample_mean + 1.5 * self.sample_stdev):.2f} {colors.END}"
                )
                self.place_order(
                    "SMALL_CHIPS",
                    self.sample_mean + 2 * self.sample_stdev,
                    min(10, self.deltas),
                    "sell",
                )

            logging.info(
                f"{colors.BEIGE2}SMALL CHIP z-edges are {((edge_ask - self.sample_mean)/self.sample_stdev):.2f} {((edge_bid - self.sample_mean)/self.sample_stdev):.2f}{colors.END} {colors.GREY}(μ={self.sample_mean:.2f},σ={self.sample_stdev:.2f}){colors.END}"
            )

    def run(self):
        if not self.exchange.is_connected():
            logging.error(f"{colors.RED}Exchange not connected.{colors.END}")
            return

        self.update_market_state()
        self.update_internal_state()

        self.print_status()
        self.send_orders()


HOST = "hackzurich-1.optibook.net"
USERNAME = "team-006"
PASSWORD = "gb7zflq0u6"


def main():
    exchange = Exchange(
        host=HOST, username=USERNAME, password=PASSWORD, info_port=7001, exec_port=8001
    )
    exchange.connect()

    bot = TradingAlgorithm(exchange)

    sleep_duration_sec = 0.3
    while True:
        bot.run()
        time.sleep(sleep_duration_sec)


if __name__ == "__main__":
    main()
