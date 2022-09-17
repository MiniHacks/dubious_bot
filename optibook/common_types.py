from datetime import datetime
from typing import List, Optional, Dict, Union
from enum import Enum
import copy
import json
import logging

logger = logging.getLogger('client')


class SingleSidedBooking:
    def __init__(self):
        self.username: str = ''
        self.instrument_id: str = ''
        self.price: float = 0.0
        self.volume: int = 0
        self.action: str = ''

    def __repr__(self):
        return f'SingleSidedBooking(username={self.username}, instrument_id={self.instrument_id}, ' \
               f'price={self.price}, volume={self.volume}, action={self.action})'


class TradeTick:
    """
    A public trade.

    A public trade is a trade between any two parties,
    i.e. a trade in which you might not have been involved.

    Attributes
    ----------
    timestamp: datetime.datetime
        The time of the trade.

    instrument_id: str
        The id of the traded instrument.

    price: float
        The price at which the instrument traded.

    volume: int
        The volume that was traded.

    aggressor_side: 'bid' or 'ask'
        The side of the aggressive party.
        If 'bid' then the initiator (aggressor) of the trade bought.
        If 'ask' then the initiator (aggressor) of the trade sold.

    buyer: str
        Name of buyer.

    seller: str
        Name of seller.

    trade_id: int
        Id of the trade
    """
    def __init__(self, *, timestamp=None, instrument_id=None, price=None, volume=None, aggressor_side=None, buyer=None, seller=None, trade_id=None):
        self.timestamp: datetime = datetime(1970, 1, 1) if not timestamp else timestamp
        self.instrument_id: str = '' if not instrument_id else instrument_id
        self.price: float = 0.0 if not price else price
        self.volume: int = 0 if not volume else volume
        self.aggressor_side: str = '' if not aggressor_side else aggressor_side
        self.buyer: str = '' if not buyer else buyer
        self.seller: str = '' if not seller else seller
        self.trade_id: int = -1 if not trade_id else trade_id

    def __repr__(self):
        return f'TradeTick(timestamp={self.timestamp}, instrument_id={self.instrument_id}, price={self.price}, ' \
               f'volume={self.volume}, aggressor_side={self.aggressor_side}, buyer={self.buyer}, ' \
               f'seller={self.seller}, trade_id={self.trade_id})'


class PriceVolume:
    """
    Bundles a price and a volume

    Attributes
    ----------
    price: float

    volume: int
    """
    def __init__(self, price, volume):
        self.price = price
        self.volume = volume

    def __repr__(self):
        return f"PriceVolume(price={str(self.price)}, volume={str(self.volume)})"

    def __eq__(self, other):
        if not isinstance(other, PriceVolume):
            return NotImplemented
        return self.price == other.price and self.volume == other.volume

    # Used for formatting
    @property
    def price_width(self):
        return len(str(round(self.price, 3))) # Currently limit price granularity to 3 d.p.

    @property
    def volume_width(self):
        return len(str(self.volume))


class PriceBook:
    """
    An order book at a specific point in time.

    Attributes
    ----------
    timestamp: datetime.datetime
        The time of the snapshot.

    instrument_id: str
        The id of the instrument the book is on.

    bids: List[PriceVolume]
        List of price points and volumes representing all bid orders.
        Sorted from highest price to lowest price (i.e. from best to worst).

    asks: List[PriceVolume]
        List of price points and volumes representing all ask orders.
        Sorted from lowest price to highest price (i.e. from best to worst).
    """
    def __init__(self, *, timestamp=None, instrument_id=None, bids=None, asks=None):
        self.timestamp: datetime = datetime(1970, 1, 1) if not timestamp else timestamp
        self.instrument_id: str = '' if not instrument_id else instrument_id
        self.bids: List[PriceVolume] = [] if not bids else bids
        self.asks: List[PriceVolume] = [] if not asks else asks

    def __repr__(self):
        book_desc = f"PriceBook({self.instrument_id} {self.timestamp})"
        book_header = ['#bids', 'price', '#asks']

        bid_width = max([bid.volume_width for bid in self.bids] + [len(book_header[0])]) + 2
        ask_width = max([ask.volume_width for ask in self.asks] + [len(book_header[2])]) + 2
        price_width = max([order.price_width for order in self.asks + self.bids] + [len(book_header[1])]) + 2

        book_repr = [book_desc, self._format_level(book_header, bid_width, price_width, ask_width)]
        for ask in self.asks[::-1]: 
            ask_level = ['', str(round(ask.price, 3)), str(ask.volume)]
            ask_level = self._format_level(ask_level, bid_width, price_width, ask_width)
            book_repr.append(ask_level)
        for bid in self.bids: 
            bid_level = [str(bid.volume), str(round(bid.price, 3)), '']
            bid_level = self._format_level(bid_level, bid_width, price_width, ask_width)
            book_repr.append(bid_level)
        return '\n'.join(book_repr)

    def __eq__(self, other):
        if not isinstance(other, PriceBook):
            return NotImplemented
        return self.instrument_id == other.instrument_id and self.bids == other.bids and self.asks == other.asks
    
    @staticmethod
    def _format_level(level: List[str], bid_width: int, price_width: int, ask_width: int):
        assert len(level) == 3, "_format_level expects 3 elements in level (#bid, price, #ask)"
        return f"{level[0].center(bid_width, ' ')}|{level[1].center(price_width, ' ')}|{level[2].center(ask_width, ' ')}"


class Trade:
    """
    A private trade.

    A private trade is a trade in which you were involved,
    i.e. a trade in which you were either a buyer or a seller.

    Attributes
    ----------
    timestamp: datetime.datetime
        The time of the trade.

    order_id: int
        The id of the order that traded.

    trade_id: int
        Id of the trade

    instrument_id: str
        The id of the traded instrument.

    price: float
        The price at which the instrument traded.

    volume: int
        The volume that was traded.

    side: 'bid' or 'ask'
        If 'bid' you bought.
        If 'ask' you sold.
    """
    def __init__(self):
        self.timestamp: datetime = datetime(1970, 1, 1)
        self.order_id: int = 0
        self.trade_id: int = -1
        self.instrument_id: str = ''
        self.price: float = 0.0
        self.volume: int = 0
        self.side: str = ''

    def __repr__(self):
        return f'Trade(timestamp={self.timestamp}, order_id={self.order_id}, trade_id={self.trade_id}, ' \
               f'instrument_id={self.instrument_id}, price={self.price}, volume={self.volume}, side={self.side})'


class OrderStatus:
    """
    Summary of an order.

    Attributes
    ----------
    order_id: int
        The id of the order.

    instrument_id: str
        The id of the traded instrument.

    price: float
        The price at which the instrument traded.

    volume: int
        The volume that was traded.

    side: 'bid' or 'ask'
        If 'bid' this is a bid order.
        If 'ask' this is an ask order.
    """
    def __init__(self):
        self.order_id: int = 0
        self.instrument_id: str = ''
        self.price: float = 0.0
        self.volume: int = 0
        self.side: str = ''

    def __repr__(self):
        return f'OrderStatus(order_id={self.order_id}, instrument_id={self.instrument_id}, price={self.price}, ' \
               f'volume={self.volume}, side={self.side})'


class InstrumentType(Enum):
    STOCK = 1
    STOCK_OPTION = 2
    STOCK_FUTURE = 3

    INDEX_TRACKING_ETF = 4

    INDEX_OPTION = 5
    INDEX_FUTURE = 6


class OptionKind(Enum):
    PUT = 1
    CALL = 2


class PriceChangeLimit:
    def __init__(self, absolute_change: float, relative_change: float):
        self.absolute_change: float = absolute_change
        self.relative_change: float = relative_change

    def __repr__(self):
        return f'PriceChangeLimit(absolute_change={self.absolute_change:.4f}, ' \
               f'relative_change={self.relative_change * 100:.2f}%)'


class Instrument:
    @staticmethod
    def from_dict(instrument_id: str, tick_size: float, price_change_limit: Optional[Union[Dict, PriceChangeLimit]],
                  dict_data: Dict) -> "Instrument":
        if price_change_limit and not isinstance(price_change_limit, PriceChangeLimit):
            price_change_limit = PriceChangeLimit(price_change_limit['absolute_change'],
                                                  price_change_limit['relative_change'])

        instrument = Instrument(instrument_id, tick_size=tick_size, price_change_limit=price_change_limit)

        # TODO: Access via getters instead of attributes?
        for k, v in dict_data.items():
            setattr(instrument, k, v)

        try:
            if instrument.instrument_type:
                instrument.instrument_type = InstrumentType[instrument.instrument_type]
            if instrument.expiry:
                instrument.expiry = datetime.strptime(instrument.expiry, '%Y-%m-%d %H:%M:%S')
            if instrument.option_kind:
                instrument.option_kind = OptionKind[instrument.option_kind]
        except:
            logger.exception(f'Error while parsing instrument {instrument_id} {tick_size} {dict_data}')

        return instrument

    @staticmethod
    def from_extra_info_json(instrument_id: str, tick_size: float, price_change_limit: Optional[PriceChangeLimit],
                             json_data: str) -> "Instrument":
        return Instrument.from_dict(instrument_id, tick_size, price_change_limit, json.loads(json_data))

    @staticmethod
    def to_extra_info_json(instrument) -> str:
        instr_copy = copy.deepcopy(instrument.__dict__)

        if instr_copy['instrument_type']:
            instr_copy['instrument_type'] = instr_copy['instrument_type'].name
        if instr_copy['expiry']:
            instr_copy['expiry'] = datetime.strftime(instr_copy['expiry'], '%Y-%m-%d %H:%M:%S')
        if instr_copy['option_kind']:
            instr_copy['option_kind'] = instr_copy['option_kind'].name

        # some fields are not part of the extra_info json
        # but are fixed fields in the protocol
        del instr_copy['instrument_id']
        del instr_copy['tick_size']
        del instr_copy['price_change_limit']
        del instr_copy['parameters']
        del instr_copy['paused']

        return json.dumps(instr_copy)

    def __init__(self,
                 instrument_id: str,
                 tick_size: float,
                 instrument_type: Optional[InstrumentType] = None,
                 price_change_limit: Optional[PriceChangeLimit] = None,
                 *,
                 expiry: Optional[datetime] = None,
                 option_kind: Optional[OptionKind] = None,
                 strike: Optional[float] = None,
                 base_instrument_id: Optional[str] = None,
                 interest_rate: Optional[float] = None,
                 index_id: Optional[float] = None,
                 index_constituents: Optional[Dict[str, float]] = None,
                 index_divisor: Optional[float] = None,
                 index_volatility: Optional[float] = None,
                 etf_cash_comp: Optional[float] = None,
                 etf_multiplier: Optional[float] = None,
                 instrument_group: Optional[str] = None):
        # All instruments
        self.instrument_id: str = instrument_id
        self.tick_size: float = tick_size
        self.instrument_type: Optional[InstrumentType] = instrument_type
        self.price_change_limit: Optional[PriceChangeLimit] = price_change_limit

        # options
        self.expiry: Optional[datetime] = expiry
        self.option_kind: Optional[OptionKind] = option_kind
        self.strike: Optional[float] = strike

        # stock options
        self.base_instrument_id: Optional[str] = base_instrument_id

        # futures and index options (stock interest rates are set by the generator)
        self.interest_rate = interest_rate

        # index etfs, futures, options
        self.index_id = index_id
        self.index_constituents = index_constituents
        self.index_divisor = index_divisor

        # index options
        self.index_volatility = index_volatility

        # etfs
        self.etf_cash_comp = etf_cash_comp
        self.etf_multiplier = etf_multiplier

        # miscellaneous
        self.instrument_group: Optional[str] = instrument_group
        self.paused: bool = False
        self.parameters: Optional[Dict] = None

    def __repr__(self):
        included_attributes = ['instrument_id', 'tick_size', 'price_change_limit', 'instrument_type',
                               'base_instrument_id', 'expiry', 'option_kind', 'strike', 'interest_rate', 'index_id',
                               'instrument_group', 'paused']
        included_attributes = filter(lambda attr: getattr(self, attr) is not None, included_attributes)
        repr = f'''Instrument({", ".join(f"{attr}={getattr(self, attr)}" for attr in included_attributes)})'''
        return repr
