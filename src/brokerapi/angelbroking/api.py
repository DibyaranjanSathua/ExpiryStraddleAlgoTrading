"""
File:           api.py
Author:         Dibyaranjan Sathua
Created on:     05/08/22, 9:52 pm
"""
from typing import Optional, List, Dict
import datetime
import time
import enum
import traceback

import requests
import pyotp
from SmartApi import SmartConnect, SmartWebSocket as SmartWebSocket_
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

from src.brokerapi.base_api import BaseApi, BrokerApiError, BrokerOrderApiError
# from src.brokerapi.angelbroking.websocketv2 import SmartWebSocketV2
from src.strategies.instrument import Instrument, Action
from src.utils.redis_backend import RedisBackend
from src.utils.logger import LogFacade


logger: LogFacade = LogFacade.get_logger("angelbroking_api")


class SmartWebSocket(SmartWebSocket_):
    """ Override __on_close method which is accepting only one arguments """

    def __on_close(self, ws, close_status_code, close_msg):
        self.HB_THREAD_FLAG = True
        print("__on_close################")
        self._on_close(ws)


class OrderConstants:
    """ Constants used while placing the order """
    class Variety(enum.Enum):
        NORMAL = "NORMAL"
        STOPLOSS = "STOPLOSS"
        AMO = "AMO"
        ROBO = "ROBO"

    class TransactionType(enum.Enum):
        BUY = "BUY"
        SELL = "SELL"

    class OrderType(enum.Enum):
        MARKET = "MARKET"
        LIMIT = "LIMIT"
        STOPLOSS_LIMIT = "STOPLOSS_LIMIT"
        STOPLOSS_MARKET = "STOPLOSS_MARKET"

    class ProductType(enum.Enum):
        DELIVERY = "DELIVERY"           # Cash & Carry for equity (CNC)
        CARRYFORWARD = "CARRYFORWARD"   # Normal for futures and options (NRML)
        MARGIN = "MARGIN"
        INTRADAY = "INTRADAY"           # Margin Intraday Squareoff (MIS)
        BO = "BO"                       # Bracket Order (Only for ROBO)

    class Duration(enum.Enum):
        DAY = "DAY"                     # Regular Order
        IOC = "IOC"                     # Immediate or Cancel

    class Exchange(enum.Enum):
        BSE = "BSE"
        NSE = "NSE"
        NFO = "NFO"
        MCX = "MCX"


class AngelBrokingApi(BaseApi):
    """ Class containing methods for connecting to AngelBroking API """

    def __init__(self, api_key: str, client_id: str, password: str, totp_key: str):
        self._api_key = api_key
        self._client_id = client_id
        self._password = password
        self._totp_key = totp_key
        self._smart_connect = SmartConnect(api_key=self._api_key)
        self._refresh_token: Optional[str] = None
        self._access_token: Optional[str] = None
        self._feed_token: Optional[str] = None
        self._market_feeds: Optional[AngelBrokingMarketFeed] = None
        self._symbol_parser: Optional[AngelBrokingSymbolParser] = None

    def login(self):
        """ Login to smart API """
        # Generate TOTP
        totp = pyotp.TOTP(self._totp_key)
        # totp = totp.now()
        attempt = 5
        while attempt > 0:
            try:
                response = self._smart_connect.generateSession(
                    self._client_id, self._password, totp.now()
                )
            except requests.exceptions.ReadTimeout as err:
                logger.warning(f"Failed to connect to login API. AngleBroking API issue.")
                logger.error(err)
                logger.info(f"Sleeping for 30 sec")
                time.sleep(30)
                continue
            if response['status']:
                break
            attempt -= 1
            logger.warning(f"Logging Failed. Trying again after 15 sec. Attempt left {attempt}")
            logger.error(response['message'])
            time.sleep(15)
        else:
            raise BrokerApiError(
                f"Error login to AngelBroking API. {response['message']}"
            )
        self._access_token = response["data"]["jwtToken"]
        self._refresh_token = response["data"]["refreshToken"]
        self._feed_token = self._smart_connect.getfeedToken()
        self._symbol_parser = AngelBrokingSymbolParser.instance()
        logger.info(f"Login successful")

    def get_user_profile(self):
        """ Return user profile """
        response = self._smart_connect.getProfile(self._refresh_token)
        if not response['status']:
            raise BrokerApiError(
                f"Error getting user profile for AngelBroking API. {response['message']}"
            )
        assert 'data' in response, "data attribute is missing in SmartAPI"
        return response["data"]

    def get_funds_and_margin(self):
        response = self._smart_connect.rmsLimit()
        if not response['status']:
            raise BrokerApiError(
                f"Error getting funds and margin for AngelBroking API. {response['message']}"
            )
        assert 'data' in response, "data attribute is missing in SmartAPI"
        return response["data"]

    def get_ltp_data(self, trading_symbol: str, symbol_token: str, exchange: str = "NSE"):
        """ Get the LTP data for trading symbol and symbol token """
        response = self._smart_connect.ltpData(
            exchange=exchange, tradingsymbol=trading_symbol, symboltoken=symbol_token
        )
        if not response['status']:
            raise BrokerApiError(
                f"Error getting lpt data for trading symbol {trading_symbol} with symbol_token "
                f"{symbol_token}. {response['message']}"
            )
        assert 'data' in response, "data attribute is missing in SmartAPI"
        return response["data"]

    def setup_market_feeds(self):
        """ Setup market feeds """
        self._market_feeds = AngelBrokingMarketFeed(
            api_key=self._api_key,
            auth_token=self._access_token,
            feed_token=self._feed_token,
            client_id=self._client_id
        )
        self._market_feeds.setup()
        # self._market_feeds.connect()

    def place_intraday_options_order(self, instrument: Instrument):
        """ Place intraday options order, Return True if order placed successfully else False """
        # Get the symbol details such as trading symbol and symbol token
        symbol_data = self.get_symbol_data(instrument)
        action = OrderConstants.TransactionType.BUY.value if instrument.action == Action.BUY \
            else OrderConstants.TransactionType.SELL.value
        logger.info(f"Placing intraday {action} order for {instrument}")
        orderparams = {
            "tradingsymbol": symbol_data["symbol"],
            "symboltoken": symbol_data["token"],
            "exchange": OrderConstants.Exchange.NFO.value,
            "transactiontype": action,
            "ordertype": OrderConstants.OrderType.MARKET.value,
            "quantity": instrument.lot_size,
            "producttype": OrderConstants.ProductType.INTRADAY.value,
            "variety": OrderConstants.Variety.NORMAL.value,
            "duration": "DAY",
        }
        attempt = 3
        while attempt > 0:
            response = None
            try:
                response = self._smart_connect.placeOrder(orderparams=orderparams)
                logger.info(f"Order Parameters: {orderparams}")
                logger.info(f"Order Response: {response}")
                instrument.order_id = response
                logger.info(
                    f"{action} order placed successfully for {instrument} with order id "
                    f"{instrument.order_id}"
                )
                if (type(response) == str and response) or \
                        (type(response) == dict and response['status']):
                    break
            except requests.exceptions.ReadTimeout as err:
                logger.warning(f"Failed to connect to order API. AngleBroking API issue.")
                logger.error(err)
                logger.exception(traceback.print_exc())
            except Exception as err:
                logger.error(f"Error placing order")
                logger.error(err)
                logger.exception(traceback.print_exc())
            attempt -= 1
            logger.warning(f"Order Failed. Trying again after 2 sec. Attempt left {attempt}")
            if response is not None and type(response) == dict and \
                    response.get('message') is not None:
                logger.error(response['message'])
            time.sleep(2)
        else:
            raise BrokerOrderApiError(
                f"Error placing order to AngelBroking API."
            )

    def get_symbol_data(self, instrument: Instrument):
        """ Get the broker symbol data """
        data = self._symbol_parser.get_symbol_data(
            ticker=instrument.index,
            strike=instrument.strike,
            expiry=instrument.expiry,
            option_type=instrument.option_type
        )
        return {"symbol": data["symbol"], "token": data["token"]}

    def get_order_book(self) -> list:
        """ Return order book data """
        attempt = 3
        while attempt > 0:
            try:
                response = self._smart_connect.orderBook()
                if response['status']:
                    assert 'data' in response, "data attribute is missing in SmartAPI"
                    return response["data"]
            except Exception as err:
                logger.error(f"Error getting order book")
                logger.error(err)
                logger.exception(traceback.print_exc())
            attempt -= 1
            logger.warning(f"Order book Failed. Trying again after 2 sec. Attempt left {attempt}")
            time.sleep(2)
        else:
            raise BrokerApiError(
                f"Error getting order book from AngelBroking API."
            )

    @property
    def market_feeds(self) -> Optional["AngelBrokingMarketFeed"]:
        return self._market_feeds


class AngelBrokingMarketFeed:
    """ Real-time market feed data using websocket """

    def __init__(self, api_key: str, auth_token: str, feed_token: str, client_id: str):
        self._api_key = api_key
        self._auth_token = auth_token
        self._feed_token = feed_token
        self._client_id = client_id
        # self._web_socket: Optional[SmartWebSocket] = None
        self._web_socket: Optional[SmartWebSocketV2] = None
        self._options_tokens = []
        self._index_tokens = []
        self._token_subscribed = []
        self._token_symbol_mapper = TokenSymbolMapper()
        self._redis_backend = RedisBackend()

    def setup(self):
        """ Setup websocket """
        # self._web_socket = SmartWebSocket(self._feed_token, self._client_id)
        self._web_socket = SmartWebSocketV2(
            self._auth_token, self._api_key, self._client_id, self._feed_token
        )
        self._web_socket.on_open = self.on_open
        self._web_socket.on_data = self.on_data
        self._web_socket.on_error = self.on_error
        self._web_socket.on_close = self.on_close

    def connect(self):
        """ Connect to websocket """
        # Connect to redis backend
        self._redis_backend.connect()
        self._web_socket.connect()

    def subscribe(self):
        """
        Subscribe to scripts.
        correlation_id: string
            A 10 character alphanumeric ID client may provide which will be returned by the server in error response
            to indicate which request generated error response.
            Clients can use this optional ID for tracking purposes between request and corresponding error response.
         mode: integer
            It denotes the subscription type
            possible values -> 1, 2 and 3
            1 -> LTP
            2 -> Quote
            3 -> Snap Quote
        """
        correlation_id = "sathualabs"
        mode = 1
        script = self.get_script()
        # script = [{"exchangeType": 1, "tokens": ["26009"]}]
        if script:
            print(f"Subscribing script: {script}")
            self._web_socket.subscribe(correlation_id, mode, script)

    def on_data(self, ws, message):
        print(f"Ticks: {message}")
        self.parse_save(message)

    def on_open(self, ws):
        print("On Open")
        self.subscribe()

    def on_error(self, ws, error):
        print("On Error")
        print(error)

    def on_close(self, ws):
        print("On Close")

    def parse_save(self, message) -> None:
        """ Parse the market websocket message and save it to redis backend """
        if type(message) == dict:
            if "token" in message and "last_traded_price" in message:
                symbol = self._token_symbol_mapper[message["token"]]
                # Redis. Key is symbol in format <NIFTY><DD><MON><YY><STRIKE><OPTIONTYPE>
                # NIFTY25AUG2217000CE and value is dict
                symbol_data = {
                    "token": message["token"],
                    "ltp": float(message["last_traded_price"]/100),
                    "timestamp": int(datetime.datetime.now().timestamp())
                }
                self._redis_backend.set(symbol, symbol_data)

    def get_option_script(self) -> dict:
        output = {}
        if self._options_tokens:
            output = {"exchangeType": 2, "tokens": self._options_tokens}
        return output

    def get_index_script(self) -> dict:
        """
        Sample Value ->
        [
            { "exchangeType": 1, "tokens": ["10626", "5290"]},
            {"exchangeType": 5, "tokens": [ "234230", "234235", "234219"]}
        ]
        exchangeType: integer
        possible values ->
            1 -> nse_cm
            2 -> nse_fo
            3 -> bse_cm
            4 -> bse_fo
            5 -> mcx_fo
            7 -> ncx_fo
            13 -> cde_fo
        tokens: list of string
        """
        output = {}
        if self._index_tokens:
            output = {"exchangeType": 1, "tokens": self._index_tokens}
        return output

    def get_script(self) -> list:
        output = []
        option_script = self.get_option_script()
        index_script = self.get_index_script()
        if index_script:
            output.append(index_script)
        if option_script:
            output.append(option_script)
        return output

    @property
    def index_tokens(self) -> List:
        return self._index_tokens

    @index_tokens.setter
    def index_tokens(self, tokens: List) -> None:
        self._index_tokens = tokens

    @property
    def options_tokens(self) -> List:
        return self._options_tokens

    @options_tokens.setter
    def options_tokens(self, tokens: List) -> None:
        self._options_tokens = tokens


class AngelBrokingSymbolParser:
    """ Angel broking symbol parsing """
    DATE_FORMAT: str = "%d%b%Y"
    __instance: Optional["AngelBrokingSymbolParser"] = None

    def __init__(self):
        self._nifty_instruments: List[Dict] = []
        self._banknifty_instruments: List[Dict] = []
        self._finnifty_instruments: List[Dict] = []
        self._nifty_current_week_expiry_instrument: List[Dict] = []
        self._banknifty_current_week_expiry_instruments: List[Dict] = []
        self._finnifty_current_week_expiry_instrument: List[Dict] = []
        self._nifty_index_token = ""
        self._banknifty_index_token = ""
        self._finnifty_index_token = ""
        self._expiry = set()
        self._current_week_expiry: Optional[datetime.date] = None

    @classmethod
    def instance(cls):
        """ Return instance of this class. This is a singleton class """
        if cls.__instance is None:
            cls.__instance = cls()
            cls.__instance._parse()
        return cls.__instance

    def _parse(self):
        """ Parse JSON data """
        response = requests.get(self.symbol_master_file)
        if response.ok:
            data = response.json()
            self._nifty_instruments = [x for x in data if x["name"] == "NIFTY"]
            self._banknifty_instruments = [x for x in data if x["name"] == "BANKNIFTY"]
            self._finnifty_instruments = [x for x in data if x["name"] == "FINNIFTY"]
        self._expiry = set(
            self.get_date_obj(x["expiry"]) for x in self._nifty_instruments if x["expiry"]
        )
        self._expiry = sorted(self._expiry)
        self._current_week_expiry = self.get_current_week_expiry()
        self._nifty_current_week_expiry_instrument = [
            x for x in self._nifty_instruments
            if x["expiry"] == self.get_date_str(self._current_week_expiry)
        ]
        self._banknifty_current_week_expiry_instruments = [
            x for x in self._banknifty_instruments
            if x["expiry"] == self.get_date_str(self._current_week_expiry)
        ]
        self._finnifty_current_week_expiry_instrument = [
            x for x in self._finnifty_instruments
            if x["expiry"] == self.get_date_str(self._current_week_expiry)
        ]
        # Get the index token. By default we will subscribe for index tokens
        self._nifty_index_token = next(
            (x["token"] for x in self._nifty_instruments if x["symbol"] == "Nifty 50"),
            None
        )
        self._banknifty_index_token = next(
            (x["token"] for x in self._banknifty_instruments if x["symbol"] == "BANKNIFTY"),
            None
        )
        self._finnifty_index_token = next(
            (x["token"] for x in self._finnifty_instruments if x["symbol"] == "Nifty Fin Service"),
            None
        )

    def get_current_week_expiry(self, signal_date: Optional[datetime.date] = None) -> datetime.date:
        """ Return current week expiry for the signal date. Signal date should be in IST """
        if signal_date is None:
            signal_date = datetime.datetime.now().date()
        return next((x for x in self._expiry if x >= signal_date), None)

    def get_symbol_data(
            self, ticker: str, strike: int, expiry: datetime.date, option_type: str
    ) -> Dict:
        """
        Get the symbol details such as token and symbol name by ticker, strike_price, expiry
        and option_type.
        """
        instruments = []
        if ticker == "NIFTY":
            instruments = self._nifty_instruments
        elif ticker == "BANKNIFTY":
            instruments = self._banknifty_instruments
        elif ticker == "FINNIFTY":
            instruments = self._finnifty_instruments
        return next(
            (
                x for x in instruments
                if self.convert_strike_to_int(x["strike"]) == strike
                   and self.get_date_obj(x["expiry"]) == expiry
                   and x["symbol"].endswith(option_type)
            ),
            None
        )

    @staticmethod
    def get_date_obj(date_str: str) -> datetime.date:
        return datetime.datetime.strptime(date_str, AngelBrokingSymbolParser.DATE_FORMAT).date()

    @staticmethod
    def get_date_str(date: datetime.date) -> str:
        return date.strftime(AngelBrokingSymbolParser.DATE_FORMAT)

    @staticmethod
    def convert_strike_to_int(strike: str) -> int:
        return int(float(strike)) // 100

    @property
    def current_week_expiry(self) -> Optional[datetime.date]:
        return self._current_week_expiry

    @property
    def nifty_index_token(self) -> str:
        return self._nifty_index_token

    @property
    def banknifty_index_token(self) -> str:
        return self._banknifty_index_token

    @property
    def finnifty_index_token(self) -> str:
        return self._finnifty_index_token

    @property
    def symbol_master_file(self) -> str:
        return "https://margincalculator.angelbroking.com/OpenAPI_File/files/" \
               "OpenAPIScripMaster.json"


class TokenSymbolMapper:
    """ Maps token to instrument symbol """
    # Instrument symbol is in format <NIFTY><DD><MON><YY><STRIKE><OPTIONTYPE>. NIFTY25AUG2217000CE
    __MAPPER = dict()

    def __getitem__(self, item: str):
        return self.__MAPPER[item]

    def __setitem__(self, key, value):
        self.__MAPPER[key] = value

    def __contains__(self, item: str):
        return item in self.__MAPPER

    def get(self, item, default=None):
        return self.__MAPPER.get(item, default=default)


if __name__ == "__main__":
    from src import BASE_DIR
    from src.utils.config_reader import ConfigReader

    config_path = BASE_DIR / 'data' / 'config.json'
    config = ConfigReader(config_file_path=config_path)
    trading_account = config["trading_accounts"][0]
    api_key = trading_account["api_key"]
    client_id = trading_account["client_id"]
    password = trading_account["password"]
    totp_key = trading_account["totp_key"]
    api = AngelBrokingApi(api_key, client_id, password, totp_key)
    api.login()
    user = api.get_user_profile()
    print(user)
    funds = api.get_funds_and_margin()
    print(funds)
    order_book = api.get_order_book()
    print(order_book)
    # data = api.get_ltp_data(trading_symbol="NIFTY", symbol_token="26000", exhange="NSE")
    # print(data)
    # api.setup_market_feeds()
    symbol_parser = AngelBrokingSymbolParser.instance()
    # symbol_parser1 = AngelBrokingSymbolParser.instance()
    # print(id(symbol_parser) == id(symbol_parser1))
    # print(symbol_parser.current_week_expiry)
    symbol_data = symbol_parser.get_symbol_data(
        ticker="FINNIFTY",
        strike=18900,
        expiry=symbol_parser.current_week_expiry,
        option_type="CE"
    )
    print(symbol_parser.finnifty_index_token)
    # instrument = Instrument(
    #         action=Action.SELL,
    #         lot_size=50,
    #         expiry=symbol_parser.current_week_expiry,
    #         option_type="CE",
    #         strike=18900,
    #         index="NIFTY",
    #         entry=datetime.datetime.now(),
    #         price=0,
    #         order_id=""
    # )
    # status = api.place_intraday_options_order(instrument)
    # print(f"Order status: {status}")
    # print(f"Order id: {instrument.order_id}")
    # funds = api.get_funds_and_margin()
    # print(funds)
    # print(instrument)
    # instrument = symbol_parser.get_symbol_data(
    #     ticker="NIFTY",
    #     strike=18000,
    #     expiry=symbol_parser.current_week_expiry,
    #     option_type="CE"
    # )
    # print(instrument)
    # print(symbol_parser.nifty_index_token)
    # print(symbol_parser.banknifty_index_token)
