import logging
import time
from optibook import ORDER_TYPE_LIMIT, SIDE_ASK, SIDE_BID
from optibook.exchange_responses import InsertOrderResponse
from optibook.synchronous_client import Exchange
from collections import defaultdict
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
        self.pnl = self.exchange.get_pnl()
        self.instruments = ["SMALL_CHIPS_NEW_COUNTRY", "SMALL_CHIPS"]
        self.book = {}
        self.is_trading = defaultdict(bool)

        tradable_instruments = self.exchange.get_instruments()
        for instrument_id in self.instruments:
            if instrument_id not in tradable_instruments:
                raise Exception(
                    f"'{instrument_id}' does not exist. Options: {tradable_instruments}"
                )

    def print_report(self):
        old_pnl, self.pnl = self.pnl, self.exchange.get_pnl()
        positions = self.exchange.get_positions()
        my_trades, all_market_trades = [], []
        for instrument_id in self.instruments:
            my_trades += self.exchange.poll_new_trades(instrument_id)
            all_market_trades += self.exchange.poll_new_trade_ticks(instrument_id)
            logging.info(
                f"{instrument_id}: bid={self.book[instrument_id].bids[0].price:.2f}, ask={self.book[instrument_id].asks[0].price:.2f}, spread={(self.book[instrument_id].asks[0].price - self.book[instrument_id].bids[0].price):.2f}"
            )
            logging.info(f"{self.book[instrument_id]}")
        logging.info(
            f"{colors.WHITE2}PNL: {old_pnl:.2f} -> {self.pnl:.2f}{colors.END}, (Δ: {c(self.pnl - old_pnl)}) \
            {colors.WHITE2}{len(my_trades)}/{len(all_market_trades)}{colors.END} trades"
        )
        logging.info(
            f"SMALL: {C(positions['SMALL_CHIPS'])} {C(positions['SMALL_CHIPS_NEW_COUNTRY'])}, δ: {C(positions['SMALL_CHIPS'] + positions['SMALL_CHIPS_NEW_COUNTRY'])}"  # \
            # TECH: {C(positions['TECH_INC'])} {C(positions['TECH_INC_NEW_COUNTRY'])}, δ: {C(positions['TECH_INC'] + positions['TECH_INC_NEW_COUNTRY'])}"
        )

    def trade_cycle(self):
        if not self.exchange.is_connected():
            print(f"{colors.RED}Exchange not connected.{colors.END}")
            return

        tradable_instruments = self.exchange.get_instruments()
        for instrument_id in self.instruments:
            self.book[instrument_id] = self.exchange.get_last_price_book(instrument_id)
            self.is_trading[instrument_id] = tradable_instruments[instrument_id]

        for instrument_id in self.instruments:
            self.exchange.delete_orders(instrument_id)

        # try to improve the best bid and best ask by 10 cents
        for instrument_id in self.instruments:
            new_bid_price = self.book[instrument_id].bids[0].price + 0.1
            new_ask_price = self.book[instrument_id].asks[0].price - 0.1
            if new_ask_price - new_bid_price > 0.01:
                bid_response: InsertOrderResponse = self.exchange.insert_order(
                    instrument_id,
                    price=new_bid_price,
                    volume=10,
                    side=SIDE_BID,
                    order_type=ORDER_TYPE_LIMIT,
                )
                print_order_response(bid_response)
                ask_response: InsertOrderResponse = self.exchange.insert_order(
                    instrument_id,
                    price=new_ask_price,
                    volume=10,
                    side=SIDE_ASK,
                    order_type=ORDER_TYPE_LIMIT,
                )
                print_order_response(ask_response)
        self.print_report()


HOST = "hackzurich-1.optibook.net"
USERNAME = "team-006"
PASSWORD = "gb7zflq0u6"


def main():
    exchange = Exchange(
        host=HOST, username=USERNAME, password=PASSWORD, info_port=7001, exec_port=8001
    )
    exchange.connect()
    time.sleep(3)

    bot = Bot(exchange)

    sleep_duration_sec = 1  # TODO: crank this
    while True:
        bot.trade_cycle()
        time.sleep(sleep_duration_sec)


if __name__ == "__main__":
    main()
