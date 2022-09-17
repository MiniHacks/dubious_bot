import logging
import time
from optibook import ORDER_TYPE_LIMIT, SIDE_ASK, SIDE_BID
from optibook.exchange_responses import InsertOrderResponse
from optibook.synchronous_client import Exchange
import colors
import json

root = logging.getLogger()
if root.handlers:
    for handler in root.handlers:
        root.removeHandler(handler)
logging.Formatter(
    datefmt="%H:%M:%S",
    fmt="%(asctime)s.%(msecs)03d",
)
logging.basicConfig(
    format=f"{colors.GREY}%(asctime)s{colors.END} %(message)s",
    level=logging.DEBUG,
)
# logging = logging.getLogger("client")

INSTRUMENT_ID = "SMALL_CHIPS_NEW_COUNTRY"


def print_order_response(order_response: InsertOrderResponse):
    if order_response.success:
        logging.info(
            f"{colors.BLUE2}Inserted order_id='{order_response.order_id}{colors.END}'"
        )
    else:
        logging.info(
            f"{colors.RED}Unable to insert order with reason: '{order_response.success}{colors.END}'"
        )


class Bot:
    def __init__(self, exchange):
        self.exchange = exchange

    def print_report(self):
        pnl = self.exchange.get_pnl()
        positions = self.exchange.get_positions()
        my_trades = self.exchange.poll_new_trades(INSTRUMENT_ID)
        all_market_trades = self.exchange.poll_new_trade_ticks(INSTRUMENT_ID)
        logging.info(
            f"Made {len(my_trades)} trade(s) in {INSTRUMENT_ID} in last epoch. \
                    {len(all_market_trades)} market trade(s) in epoch."
        )
        logging.info(f"PNL: {pnl:.2f}")
        logging.info(f"positions: {json.dumps(positions, indent=3)}")

    def check_invariants(self):
        tradable_instruments = self.exchange.get_instruments()

        if INSTRUMENT_ID not in tradable_instruments:
            return f"'{INSTRUMENT_ID}' does not exist. Options: {tradable_instruments}"

        if tradable_instruments[INSTRUMENT_ID].paused:
            return f"'{INSTRUMENT_ID}' is paused."

        if not self.book or not self.book.bids or not self.book.asks:
            return f"'{INSTRUMENT_ID}' book error: {self.book}'"

        return ""

    def trade_cycle(self):
        if not self.exchange.is_connected():
            print(f"{colors.RED}Exchange not connected.{colors.END}")
            return
        self.book = self.exchange.get_last_price_book(INSTRUMENT_ID)

        if error := self.check_invariants():
            logging.error(error)
            return

        self.exchange.delete_orders(INSTRUMENT_ID)  # remove resting
        logging.info(
            f"Order book for {INSTRUMENT_ID}: best bid={self.book.bids[0].price:.2f}, best ask={self.book.asks[0].price:.2f}"
        )
        # try to improve the best bid and best ask by 10 cents
        new_bid_price = self.book.bids[0].price + 0.1
        new_ask_price = self.book.asks[0].price - 0.1
        if new_ask_price - new_bid_price > 0.01:
            bid_response: InsertOrderResponse = self.exchange.insert_order(
                INSTRUMENT_ID,
                price=new_bid_price,
                volume=1,
                side=SIDE_BID,
                order_type=ORDER_TYPE_LIMIT,
            )
            print_order_response(bid_response)
            ask_response: InsertOrderResponse = self.exchange.insert_order(
                INSTRUMENT_ID,
                price=new_ask_price,
                volume=1,
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

    bot = Bot(exchange)

    sleep_duration_sec = 1  # TODO: crank this
    while True:
        bot.trade_cycle()
        time.sleep(sleep_duration_sec)


if __name__ == "__main__":
    main()
