import logging
import statistics
import time
from optibook import ORDER_TYPE_LIMIT, SIDE_ASK, SIDE_BID
from optibook.exchange_responses import InsertOrderResponse
from optibook.synchronous_client import Exchange
from collections import defaultdict
from functools import reduce
import colors

LEVEL = 0.1

root = logging.getLogger()
if root.handlers:
    for handler in root.handlers:
        root.removeHandler(handler)
logging.basicConfig(
    datefmt="%H:%M:%S",
    format=f"{colors.GREY}%(asctime)s.%(msecs)03d{colors.END} %(message)s",
    level=logging.DEBUG,
)


def print_order_response(order_response: InsertOrderResponse):
    if order_response.success:
        logging.info(
            f"{colors.BLUE2}Inserted order_id='{order_response.order_id}{colors.END}'"
        )
    else:
        logging.info(
            f"{colors.RED}Unable to insert order: '{order_response.success}{colors.END}'"
        )


def c(x):
    if x > 0:
        return f"{colors.GREEN}{x:.2f}{colors.END}"
    elif x < 0:
        return f"{colors.RED}{x:.2f}{colors.END}"
    else:
        return f"{colors.GREY}{x:.2f}{colors.END}"


def C(x):
    if x > 0:
        return f"{colors.GREEN}{x}{colors.END}"
    elif x < 0:
        return f"{colors.RED}{x}{colors.END}"
    else:
        return f"{colors.GREY}{x}{colors.END}"


class Bot:
    def __init__(self, exchange):
        self.exchange = exchange
        self.prev_pnl = self.pnl = self.exchange.get_pnl()
        self.instruments = ["SMALL_CHIPS_NEW_COUNTRY", "SMALL_CHIPS"]
        self.is_trading = defaultdict(bool)
        self.own_trades = defaultdict(list)
        self.market_trades = defaultdict(list)

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
        self.volume_curve = [1, 4, 9, 16]

    def place_order(self, instrument_id, price, volume, side):
        bid_response: InsertOrderResponse = self.exchange.insert_order(
            instrument_id,
            price=price,
            volume=volume,
            side=(SIDE_BID if side == "bid" else SIDE_ASK),
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

        print(theo, margin)
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
        print(prices)
        mean, stdev = statistics.mean(prices), statistics.stdev(prices)
        exemplars = list(filter(lambda x: abs(mean - x.price) <= 2 * stdev, ticks))

        theo = reduce(ema_aggregate, exemplars, exemplars[0].price)
        # TODO: tweak multiplier
        margin = stdev
        return theo, margin

    def print_status(self):
        my_trades, all_market_trades = [], []
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
            f"{colors.WHITE2}PNL: {self.prev_pnl:.2f} -> {self.pnl:.2f}{colors.END}, (Δ: {c(self.pnl - self.prev_pnl)}) \
            {colors.WHITE2}{len(my_trades)}/{len(all_market_trades)}{colors.END} trades"
        )
        logging.info(
            f"SMALL: {C(self.positions['SMALL_CHIPS'])} {C(self.positions['SMALL_CHIPS_NEW_COUNTRY'])}, δ: {C(self.positions['SMALL_CHIPS'] + self.positions['SMALL_CHIPS_NEW_COUNTRY'])}"  # \
            # TECH: {C(positions['TECH_INC'])} {C(positions['TECH_INC_NEW_COUNTRY'])}, δ: {C(positions['TECH_INC'] + positions['TECH_INC_NEW_COUNTRY'])}"
        )

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
        for trade in (
            self.own_trades["SMALL_CHIPS"] + self.own_trades["SMALL_CHIPS_NEW_COUNTRY"]
        ):
            print(self.own_trades)
            SCALAR = 0.1
            theo_delta = (
                SCALAR
                * trade.volume
                * (trade.price - self.theo)
                * (1 if trade.side == "ask" else -1)
            )
            print(f"{colors.VIOLET2}{theo_delta}{colors.END}")
            self.theo += theo_delta
            self.margin += abs(theo_delta)
        print(f"{colors.VIOLET2}{self.theo} {self.margin}{colors.END}")

    def send_orders(self):

        # this will be removed eventually
        for instrument_id in self.instruments:
            self.exchange.delete_orders(instrument_id)

        if self.is_trading["SMALL_CHIPS_NEW_COUNTRY"]:
            bids = self.book["SMALL_CHIPS_NEW_COUNTRY"].bids
            asks = self.book["SMALL_CHIPS_NEW_COUNTRY"].bids

            edge_bid, edge_ask = (
                bids[0].price if bids else 0,
                asks[0].price if asks else 1e7,
            )

            start_bid = min(edge_bid + 0.1, round(self.theo - self.margin - 0.05, 1))
            start_ask = max(edge_ask - 0.1, round(self.theo - self.margin + 0.05, 1))
            logging.info(
                f"{colors.VIOLET2}{self.theo:.2f}±{self.margin:.2f}: {start_bid:.2f} @ {start_ask:.2f}{colors.END}"
            )

            self.place_quotes_levels("SMALL_CHIPS_NEW_COUNTRY", start_bid, "bid")
            self.place_quotes_levels("SMALL_CHIPS_NEW_COUNTRY", start_ask, "ask")

        # TODO: hacks

        if self.is_trading["SMALL_CHIPS"]:
            bids = self.book["SMALL_CHIPS"]
            asks = self.book["SMALL_CHIPS"]
            # TODO: δ hedge

    def run(self):
        if not self.exchange.is_connected():
            print(f"{colors.RED}Exchange not connected.{colors.END}")
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

    bot = Bot(exchange)

    sleep_duration_sec = 1  # TODO: crank this
    while True:
        bot.run()
        time.sleep(sleep_duration_sec)


if __name__ == "__main__":
    main()
