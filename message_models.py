from pydantic import BaseModel, validator
from typing import Union, List, Optional, Mapping, Dict

# TODO: clean up polymarket specific models as we develop the callback workers


class EpochBase(BaseModel):
    begin: int
    end: int


class EpochBroadcast(EpochBase):
    broadcast_id: str


class EpochConsensusReport(EpochBase):
    reorg: bool = False


class SystemEpochStatusReport(EpochBase):
    broadcast_id: str
    reorg: bool = False


class PowerloomCallbackEpoch(SystemEpochStatusReport):
    contracts: List[str]


class PowerloomCallbackProcessMessage(SystemEpochStatusReport):
    contract: str
    coalesced_broadcast_ids: Optional[List[str]] = None
    coalesced_epochs: Optional[List[EpochBase]] = None


class RPCNodesObject(BaseModel):
    NODES: List[str]
    RETRY_LIMIT: int


class ProcessHubCommand(BaseModel):
    command: str
    pid: Optional[int] = None
    proc_str_id: Optional[str] = None
    init_kwargs: Optional[dict] = dict()


class UniswapPairTotalReservesSnapshot(BaseModel):
    contract: str
    token0Reserves: Dict[str, float]  # block number to corresponding total reserves
    token1Reserves: Dict[str, float]  # block number to corresponding total reserves
    token0ReservesUSD: Dict[str, float]
    token1ReservesUSD: Dict[str, float]
    chainHeightRange: EpochBase
    broadcast_id: str
    timestamp: float


class logsTradeModel(BaseModel):
    logs: List
    trades: Dict[str, float]


class UniswapTradesSnapshot(BaseModel):
    contract: str
    totalTrade: float  # in USD
    totalFee: float # in USD
    token0TradeVolume: float  # in token native decimals supply
    token1TradeVolume: float  # in token native decimals supply
    token0TradeVolumeUSD: float
    token1TradeVolumeUSD: float
    events: Dict[str, logsTradeModel]
    recent_logs: list
    chainHeightRange: EpochBase
    broadcast_id: str
    timestamp: float


class ethLogRequestModel(BaseModel):
    fromBlock: int = None
    toBlock: int = None
    contract: str = None
    topics: list = None
    requestId: str = None
    retrialCount: int = 1
