from datetime import datetime
from .common_types import InstrumentType, OptionKind, Instrument


def validate_instrument(instrument: Instrument) -> None:
    if not instrument.instrument_id or not instrument.tick_size:
        raise Exception("Invalid instrument definition: instrument id or tick_size is not defined.")

    if instrument.tick_size <= 0:
        raise Exception("Invalid instrument definition: tick_size must be positive.")

    # it's okay to not have an instrument type (e.g. MM_GAME_1)
    if not instrument.instrument_type:
        return

    if instrument.instrument_type == InstrumentType.STOCK:
        _is_stock(instrument)
        return
    elif instrument.instrument_type == InstrumentType.STOCK_FUTURE:
        _is_stock_future(instrument)
        return
    elif instrument.instrument_type == InstrumentType.STOCK_OPTION:
        _is_stock_option(instrument)
        return
    elif instrument.instrument_type == InstrumentType.INDEX_TRACKING_ETF:
        _is_index_tracking_etf(instrument)
        return
    elif instrument.instrument_type == InstrumentType.INDEX_FUTURE:
        _is_index_future(instrument)
        return
    elif instrument.instrument_type == InstrumentType.INDEX_OPTION:
        _is_index_option(instrument)
        return

    else:
        raise Exception(f"Invalid instrument definition: instrument_type not known: {instrument.instrument_type}.")


def _is_stock(instrument: Instrument) -> None:
    if instrument.base_instrument_id:
        raise Exception("Invalid STOCK definition: should not have a base_instrument_id.")

    if instrument.expiry:
        raise Exception("Invalid STOCK definition: should not have an expiry.")

    if instrument.option_kind:
        raise Exception("Invalid STOCK definition: should not have an option_kind.")

    if instrument.strike:
        raise Exception("Invalid STOCK definition: should not have a strike.")


def _is_stock_future(instrument: Instrument) -> None:
    # NOTE: This does not (yet) check the instrument type or even the existence of the base instrument. We do not want
    #  to enforce it being created before its derivatives.

    if not instrument.interest_rate:
        raise Exception("Invalid STOCK_FUTURE definition: should have interest_rate")

    if not instrument.base_instrument_id:
        raise Exception("Invalid STOCK_FUTURE definition: base_instrument_id is not defined.")

    if not instrument.expiry:
        raise Exception("Invalid STOCK_FUTURE definition: expiry is not defined.")

    if instrument.expiry < datetime.now():
        raise Exception("Invalid STOCK_FUTURE definition: expiry must be in the future.")

    if instrument.option_kind:
        raise Exception("Invalid STOCK_FUTURE definition: should not have an option_kind.")

    if instrument.strike:
        raise Exception("Invalid STOCK_FUTURE definition: should not have a strike.")


def _is_stock_option(instrument: Instrument) -> None:
    # NOTE: This does not (yet) check the instrument type or even the existence of the base instrument. We do not want
    #  to enforce it being created before its derivatives.

    # TODO: Resolve: Instrument structures are inconsistent between stock options and other derivatives, sigma and
    #  interest_rate are stored as part of the stock, not the option; in other derivatives (FUTURES) the rate is part
    #  of the future definition, which works well in those contexts.

    if not instrument.base_instrument_id:
        raise Exception("Invalid STOCK_OPTION definition: base_instrument_id is not defined.")

    if not instrument.expiry:
        raise Exception("Invalid STOCK_OPTION definition: expiry is not defined.")

    if instrument.expiry < datetime.now():
        raise Exception("Invalid STOCK_OPTION definition: expiry must be in the future.")

    if not instrument.option_kind:
        raise Exception("Invalid STOCK_OPTION definition: option_kind is not defined.")

    if instrument.option_kind != OptionKind.PUT and instrument.option_kind != OptionKind.CALL:
        raise Exception("Invalid STOCK_OPTION definition: option_kind must be OptionKind.PUT or OptionKind.CALL.")

    if not instrument.strike:
        raise Exception("Invalid STOCK_OPTION definition: strike is not defined.")

    if float(instrument.strike) <= 0:
        raise Exception("Invalid STOCK_OPTION definition: strike must be positive.")


def _is_index_tracking_etf(instrument: Instrument) -> None:
    if not instrument.index_id:
        raise Exception("Invalid INDEX_TRACKING_ETF definition: should have index_id")

    if not instrument.index_constituents:
        # NOTE: We don't check the contents of index_constituents for proper structure, should we?
        raise Exception("Invalid INDEX_TRACKING_ETF definition: should have index_constituents")

    if not instrument.index_divisor:
        raise Exception("Invalid INDEX_TRACKING_ETF definition: should have index_divisor")

    if not instrument.etf_cash_comp:
        raise Exception("Invalid INDEX_TRACKING_ETF definition: should have etf_cash_comp")

    if not instrument.etf_multiplier:
        raise Exception("Invalid INDEX_TRACKING_ETF definition: should have etf_multiplier")

    if instrument.base_instrument_id:
        raise Exception("Invalid INDEX_TRACKING_ETF definition: should not have a base_instrument_id.")

    if instrument.expiry:
        raise Exception("Invalid INDEX_TRACKING_ETF definition: should not have an expiry.")

    if instrument.option_kind:
        raise Exception("Invalid INDEX_TRACKING_ETF definition: should not have an option_kind.")

    if instrument.strike:
        raise Exception("Invalid INDEX_TRACKING_ETF definition: should not have a strike.")


def _is_index_future(instrument: Instrument) -> None:
    if not instrument.index_id:
        raise Exception("Invalid INDEX_FUTURE definition: should have index_id")

    if not instrument.index_constituents:
        # NOTE: We don't check the contents of index_constituents for proper structure, should we?
        raise Exception("Invalid INDEX_FUTURE definition: should have index_constituents")

    if not instrument.index_divisor:
        raise Exception("Invalid INDEX_FUTURE definition: should have index_divisor")

    if not instrument.interest_rate:
        raise Exception("Invalid INDEX_FUTURE definition: should have interest_rate")

    if not instrument.expiry:
        raise Exception("Invalid INDEX_FUTURE definition: expiry is not defined.")

    if instrument.expiry < datetime.now():
        raise Exception("Invalid INDEX_FUTURE definition: expiry must be in the future.")

    if instrument.option_kind:
        raise Exception("Invalid INDEX_FUTURE definition: should not have an option_kind.")

    if instrument.strike:
        raise Exception("Invalid INDEX_FUTURE definition: should not have a strike.")


def _is_index_option(instrument: Instrument) -> None:
    if not instrument.index_id:
        raise Exception("Invalid INDEX_OPTION definition: should have index_id")

    if not instrument.index_constituents:
        # NOTE: We don't check the contents of index_constituents for proper structure, should we?
        raise Exception("Invalid INDEX_OPTION definition: should have index_constituents")

    if not instrument.interest_rate:
        raise Exception("Invalid INDEX_OPTION definition: should have interest_rate")

    if not instrument.index_divisor:
        raise Exception("Invalid INDEX_OPTION definition: should have index_divisor")

    if not instrument.index_volatility:
        raise Exception("Invalid INDEX_OPTION definition: should have index_volatility")

    if not instrument.expiry:
        raise Exception("Invalid INDEX_OPTION definition: expiry is not defined.")

    if instrument.expiry < datetime.now():
        raise Exception("Invalid INDEX_OPTION definition: expiry must be in the future.")

    if not instrument.option_kind:
        raise Exception("Invalid INDEX_OPTION definition: option_kind is not defined.")

    if instrument.option_kind != OptionKind.PUT and instrument.option_kind != OptionKind.CALL:
        raise Exception("Invalid INDEX_OPTION definition: option_kind must be OptionKind.PUT or OptionKind.CALL.")

    if not instrument.strike:
        raise Exception("Invalid INDEX_OPTION definition: strike is not defined.")

    if float(instrument.strike) <= 0:
        raise Exception("Invalid INDEX_OPTION definition: strike must be positive.")

