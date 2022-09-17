import logging
import statistics
import time
from optibook import ORDER_TYPE_LIMIT, SIDE_ASK, SIDE_BID
from optibook.exchange_responses import InsertOrderResponse
from optibook.synchronous_client import Exchange
from collections import defaultdict
from functools import reduce
import colors

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

        print(self.theo)
        print(self.margin)
        for v in self.book.values():
            print(v)
        input()

    def compute_market_book(self):
        book = self.book["SMALL_CHIPS"]
        ask = book.asks[0]
        bid = book.bids[0]

        while not self.book["SMALL_CHIPS"]:
            time.sleep(1)
            self.book["SMALL_CHIPS"] = self.exchange.get_last_price_book("SMALL_CHIPS")
        theo = (ask.price * ask.volume + bid.price + bid.volume) / (
            bid.volume + ask.volume
        )
        margin = (ask.price - bid.price) / 2

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
            self.is_trading[instrument_id] = tradable_instruments[instrument_id]

            self.own_trades[instrument_id] = self.exchange.poll_new_trades(
                instrument_id
            )
            self.market_trades[instrument_id] = self.exchange.poll_new_trade_ticks(
                instrument_id
            )

    def send_orders(self):

        # this will be removed eventually
        for instrument_id in self.instruments:
            self.exchange.delete_orders(instrument_id)

        for instrument_id in self.instruments:
            if self.book[instrument_id].bids:
                new_bid_price = self.book[instrument_id].bids[0].price + 0.1
            else:
                new_bid_price = self.book["SMALL_CHIPS"].bids[0].price
            if self.book[instrument_id].asks:
                new_ask_price = self.book[instrument_id].asks[0].price - 0.1
            else:
                new_ask_price = self.book["SMALL_CHIPS"].asks[0].price

            if new_ask_price - new_bid_price > 0.01:
                bid_response: InsertOrderResponse = self.exchange.insert_order(
                    instrument_id,
                    price=new_bid_price,
                    volume=3,
                    side=SIDE_BID,
                    order_type=ORDER_TYPE_LIMIT,
                )
                print_order_response(bid_response)
                ask_response: InsertOrderResponse = self.exchange.insert_order(
                    instrument_id,
                    price=new_ask_price,
                    volume=3,
                    side=SIDE_ASK,
                    order_type=ORDER_TYPE_LIMIT,
                )
                print_order_response(ask_response)

    def run(self):
        if not self.exchange.is_connected():
            print(f"{colors.RED}Exchange not connected.{colors.END}")
            return

        self.update_market_state()
        self.print_status()

        for i in self.instruments:
            print("VVV----------VVV")
            for trade in self.own_trades[i]:
                print(trade)
            print("----------------")
            for trade in self.market_trades[i]:
                print(trade)
            print("^^^----------^^^")

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
