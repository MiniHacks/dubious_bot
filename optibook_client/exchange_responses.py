from typing import Optional


class InsertOrderResponse:
    """
    The exchange response upon inserting an order.

    Attributes
    ----------
    success: bool
        A success flag indicating whether the request was successful or not. If it was, order_id is set, otherwise
        error_reason is set.
    order_id: Optional[int]
        The id of the order which was inserted. The order_id can be used to delete or amend a limit order later.
        If None, the order insertion failed, and an error_reason will be set.
    error_reason: Optional[str]
        An error reason in case the insert was not successful.
    """
    def __init__(self, success: bool, order_id: Optional[int], error_reason: Optional[str]):
        self.success: bool = success
        self.order_id: Optional[int] = order_id
        self.error_reason: Optional[str] = error_reason

    def __repr__(self):
        return f"InsertOrderResponse(success={self.success}, order_id={self.order_id}, error_reason='{self.error_reason}')"


class AmendOrderResponse:
    """
    The exchange response upon amending an order.

    Attributes
    ----------
    success: bool
        A success flag indicating whether the request was successful or not. If it was not, error_reason is set.
    error_reason: Optional[str]
        An error reason in case the insert was not successful.
    """
    def __init__(self, success: bool, error_reason: Optional[str]):
        self.success: Optional[int] = success
        self.error_reason: Optional[str] = error_reason

    def __repr__(self):
        return f"AmendOrderResponse(success={self.success}, error_reason='{self.error_reason}')"


class DeleteOrderResponse:
    """
    The server response upon deleting an order.

    Attributes
    ----------
    success: bool
        A success flag indicating whether the request was successful or not. If it was not, error_reason is set.
    error_reason: Optional[str]
        An error reason in case the insert was not successful.
    """
    def __init__(self, success: bool, error_reason: Optional[str]):
        self.success: Optional[int] = success
        self.error_reason: Optional[str] = error_reason

    def __repr__(self):
        return f"DeleteOrderResponse(success={self.success}, error_reason='{self.error_reason}')"

