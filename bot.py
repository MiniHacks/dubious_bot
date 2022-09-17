import logging
import time
from optibook import ORDER_TYPE_LIMIT, SIDE_ASK, SIDE_BID
from optibook.exchange_responses import InsertOrderResponse
from optibook.synchronous_client import Exchange
import colors
import json

logging.getLogger("client").setLevel("ERROR")
logger = logging.getLogger(__name__)

INSTRUMENT_ID = "SMALL_CHIPS"


def print_report(e: Exchange):
    pnl = e.get_pnl()
    positions = e.get_positions()
    my_trades = e.poll_new_trades(INSTRUMENT_ID)
    all_market_trades = e.poll_new_trade_ticks(INSTRUMENT_ID)
    logger.info(
        f"{len(my_trades)} trade(s) in {INSTRUMENT_ID} since the last report.\
            There have been {len(all_market_trades)} market trade(s) in total \
            in {INSTRUMENT_ID} since the last report."
    )
    logger.info(f"My PNL is: {pnl:.2f}")
    logger.info(f"My current positions are: {json.dumps(positions, indent=3)}")


def print_order_response(order_response: InsertOrderResponse):
    if order_response.success:
        logger.info(
            f"{colors.BLUE2}Inserted order_id='{order_response.order_id}{colors.END}'"
        )
    else:
        logger.info(
            f"{colors.RED}Unable to insert order with reason: '{order_response.success}{colors.END}'"
        )


class bot:
    def __init__(self):
        # TODO fix me
        pass

    def check_invariants(self):
        tradable_instruments = exchange.get_instruments()

        if INSTRUMENT_ID not in tradable_instruments:
            return f"'{INSTRUMENT_ID}' does not exist."

        if tradable_instruments[INSTRUMENT_ID].paused:
            return f"'{INSTRUMENT_ID}' is paused."

        return ""

    def trade_cycle(self, e: Exchange):

        if error := self.check_invariants():
            logger.error(error)
            return

        # because we use limit orders, always delete existing orders that remain from the previous iteration
        e.delete_orders(INSTRUMENT_ID)
        book = e.get_last_price_book(INSTRUMENT_ID)
        if book and book.bids and book.asks:
            logger.info(
                f"Order book for {INSTRUMENT_ID}: best bid={book.bids[0].price:.2f}, best ask={book.asks[0].price:.2f}"
            )
            # try to improve the best bid and best ask by 10 cents
            new_bid_price = book.bids[0].price + 0.1
            new_ask_price = book.asks[0].price - 0.1
            if new_ask_price - new_bid_price > 0.01:
                bid_response: InsertOrderResponse = e.insert_order(
                    INSTRUMENT_ID,
                    price=new_bid_price,
                    volume=1,
                    side=SIDE_BID,
                    order_type=ORDER_TYPE_LIMIT,
                )
                print_order_response(bid_response)
                ask_response: InsertOrderResponse = e.insert_order(
                    INSTRUMENT_ID,
                    price=new_ask_price,
                    volume=1,
                    side=SIDE_ASK,
                    order_type=ORDER_TYPE_LIMIT,
                )
                print_order_response(ask_response)
            else:
                logger.info(
                    f"Order book is already too tight to improve further!")
        else:
            logger.info(
                f"No top bid/ask or no book at all for the instrument '{INSTRUMENT_ID}'"
            )

        print_report(e)


def main():
    exchange = Exchange()
    exchange.connect()

    # you can also define host/user/pass yourself
    # when not defined, it is taken from ~/.optibook file if it exists
    # if that file does not exists, an error is thrown
    # exchange = Exchange(host='host-to-connect-to', info_port=7001, exec_port=8001, username='your-username', password='your-password')
    # exchange.connect()

    sleep_duration_sec = 5
    while True:
        trade_cycle(exchange)
        logger.info(
            f"Iteration complete. Sleeping for {sleep_duration_sec} seconds")
        time.sleep(sleep_duration_sec)


if __name__ == "__main__":
    main()
