import typing as T

from eth_typing import Address


class ListFilters:
    BUY_NOW = "buy_now"
    HAS_OFFERS = "has_offers"
    ON_AUCTION = "on_auction"
    UNLISTED = "unlisted"


class Activity(T.TypedDict):
    activityType: str
    collection: str
    collectionName: str
    collectionSymbol: str
    name: str
    image: str
    tokenId: str
    fromAddress: Address
    toAddress: Address
    quantity: int
    timestamp: int
    transactionHash: str
    currency: str
    price: str
    orderHash: str
    orderNonce: str
    isTakerAsk: str
    strategy: str
    status: str
    auctionStatus: str
    auctionType: str
