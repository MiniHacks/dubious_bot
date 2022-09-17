import logging
import time
from optibook import ORDER_TYPE_LIMIT, SIDE_ASK, SIDE_BID
from optibook.exchange_responses import InsertOrderResponse
from optibook.synchronous_client import Exchange
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

INSTRUMENT_ID = "SMALL_CHIPS_NEW_COUNTRY"


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
        self.pnl = 0

    def print_report(self):
        old_pnl, self.pnl = self.pnl, self.exchange.get_pnl()
        positions = self.exchange.get_positions()
        my_trades = self.exchange.poll_new_trades(INSTRUMENT_ID)
        all_market_trades = self.exchange.poll_new_trade_ticks(INSTRUMENT_ID)
        logging.info(
            f"{colors.WHITE2}PNL: {old_pnl:.2f} -> {self.pnl:.2f}{colors.END}, (Δ: {c(self.pnl - old_pnl)}) \
            {colors.WHITE2}{len(my_trades)}/{len(all_market_trades)}{colors.END} trades"
        )
        logging.info(
            f"SMALL: {C(positions['SMALL_CHIPS'])} {C(positions['SMALL_CHIPS_NEW_COUNTRY'])}, δ: {C(positions['SMALL_CHIPS'] + positions['SMALL_CHIPS_NEW_COUNTRY'])}"  # \
            # TECH: {C(positions['TECH_INC'])} {C(positions['TECH_INC_NEW_COUNTRY'])}, δ: {C(positions['TECH_INC'] + positions['TECH_INC_NEW_COUNTRY'])}"
        )
        logging.info(self.book[INSTRUMENT_ID])
        logging.info(self.book[INSTRUMENT_ID])

    def check_invariants(self):
        tradable_instruments = self.exchange.get_instruments()

        if INSTRUMENT_ID not in tradable_instruments:
            return f"'{INSTRUMENT_ID}' does not exist. Options: {tradable_instruments}"

        if tradable_instruments[INSTRUMENT_ID].paused:
            return f"'{INSTRUMENT_ID}' is paused."

        if (
            not self.book[INSTRUMENT_ID]
            or not self.book[INSTRUMENT_ID].bids
            or not self.book[INSTRUMENT_ID].asks
        ):
            return f"'{INSTRUMENT_ID}' book error: {self.book[INSTRUMENT_ID]}'"

        return ""

    def trade_cycle(self):
        if not self.exchange.is_connected():
            print(f"{colors.RED}Exchange not connected.{colors.END}")
            return
        self.book[INSTRUMENT_ID] = self.exchange.get_last_price_book(INSTRUMENT_ID)

        if error := self.check_invariants():
            logging.error(error)
            return

        self.print_report()

        self.exchange.delete_orders(INSTRUMENT_ID)
        logging.info(
            f"{INSTRUMENT_ID}: bid={self.book[INSTRUMENT_ID].bids[0].price:.2f}, ask={self.book[INSTRUMENT_ID].asks[0].price:.2f}, spread={(self.book[INSTRUMENT_ID].asks[0].price - self.book[INSTRUMENT_ID].bids[0].price):.2f}"
        )
        # try to improve the best bid and best ask by 10 cents
        new_bid_price = self.book[INSTRUMENT_ID].bids[0].price + 0.1
        new_ask_price = self.book[INSTRUMENT_ID].asks[0].price - 0.1
        if new_ask_price - new_bid_price > 0.01:
            bid_response: InsertOrderResponse = self.exchange.insert_order(
                INSTRUMENT_ID,
                price=new_bid_price,
                volume=10,
                side=SIDE_BID,
                order_type=ORDER_TYPE_LIMIT,
            )
            print_order_response(bid_response)
            ask_response: InsertOrderResponse = self.exchange.insert_order(
                INSTRUMENT_ID,
                price=new_ask_price,
                volume=10,
                side=SIDE_ASK,
                order_type=ORDER_TYPE_LIMIT,
            )
            print_order_response(ask_response)


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
