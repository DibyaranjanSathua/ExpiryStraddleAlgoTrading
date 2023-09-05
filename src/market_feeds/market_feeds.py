"""
File:           market_feeds.py
Author:         Dibyaranjan Sathua
Created on:     09/08/22, 8:32 pm
"""
from typing import List, Optional
import datetime

from src.brokerapi.angelbroking import AngelBrokingApi, AngelBrokingSymbolParser, \
    TokenSymbolMapper
from src.utils import StrategyTicker


class MarketFeeds:
    """ Store the live market feeds in redis db """
    def __init__(
            self,
            api_key: str,
            client_id: str,
            password: str,
            totp_key: str,
            symbol_parser: AngelBrokingSymbolParser,
            only_ce_or_pe: bool = True,
            option_type: str = "CE"
    ):
        self._api_key = api_key
        self._client_id = client_id
        self._password = password
        # When only one broker account is used, we will fetch 25 CE strikes and 25 PE strikes
        # If 2 broker account is used, we will fetch 50 CE strikes from one account and
        # 50 PE strikes from the other account.
        # When only_ce_or_pe is True, we will only fetch either 50 CE strikes or 50 PE strikes
        # depending on option_type.
        # If only_ce_or_pe is False, we will fetch both CE and PE strikes and option_type argument
        # is ignored.
        self._only_ce_or_pe = only_ce_or_pe
        self._option_type = option_type
        self._api = AngelBrokingApi(
            api_key=api_key, client_id=client_id, password=password, totp_key=totp_key
        )
        self._symbol_parser = symbol_parser
        self._option_tokens = []        # Stores the token for subscribing for web socket data
        self._token_symbol_mapper = TokenSymbolMapper()
        self._ticker = StrategyTicker.get_instance().ticker

    def setup(self):
        """ Setup required data for live market feeds """
        self._api.login()
        # Just to check if login is successful, fetch user profile
        self._api.get_user_profile()
        # Get the nifty ltp to determine the ATM price
        symbol_token = self._symbol_parser.nifty_index_token
        if self._ticker == "NIFTY":
            symbol_token = self._symbol_parser.nifty_index_token
        elif self._ticker == "FINNIFTY":
            symbol_token = self._symbol_parser.finnifty_index_token
        data = self._api.get_ltp_data(
            trading_symbol=self._ticker,
            symbol_token=symbol_token,
            exchange="NSE"
        )
        # Added index to token to symbol mapper
        self._token_symbol_mapper[symbol_token] = self._ticker
        index = data["ltp"]
        atm = self.get_nearest_50_strike(index)
        pe_strikes = None
        ce_strikes = None
        if self._only_ce_or_pe:
            # From one account we get fetch 50 CE strikes and other account 50 PE strikes
            if self._option_type == "CE":
                ce_strikes = [atm + (50 * x) for x in range(30)]  # 30 CE strikes (ATM + OTM)
                ce_strikes += [atm - (50 * x) for x in range(1, 20)]  # 20 CE strikes ITM
            else:
                pe_strikes = [atm - (50 * x) for x in range(30)]  # 35 PE strikes (ATM + OTM)
                pe_strikes += [atm + (50 * x) for x in range(1, 20)]  # 20 PE strikes ITM
        else:
            ce_strikes = [atm + (50 * x) for x in range(30)]    # 30 CE strikes (ATM + OTM)
            ce_strikes += [atm - (50 * x) for x in range(1, 20)]  # 20 CE strikes ITM
            pe_strikes = [atm - (50 * x) for x in range(30)]    # 30 PE strikes (ATM + OTM)
            pe_strikes += [atm + (50 * x) for x in range(1, 20)]    # 20 PE strikes ITM
        # Get the current expiry
        current_expiry = self._symbol_parser.current_week_expiry
        self._option_tokens = self.get_option_tokens(
            expiry=current_expiry, ce_strikes=ce_strikes, pe_strikes=pe_strikes
        )
        # Setup market feed
        self._api.setup_market_feeds()
        self._api.market_feeds.options_tokens = self._option_tokens
        self._api.market_feeds.index_tokens = [symbol_token]
        self._api.market_feeds.connect()

    def get_option_tokens(
            self,
            expiry: datetime.date,
            *,
            ce_strikes: Optional[List] = None,
            pe_strikes: Optional[List] = None
    ):
        """ Get the option tokens for ce_strikes and pe_strikes """
        option_tokens = []
        date_str = expiry.strftime("%d%b%y").upper()
        for strike in ce_strikes or []:
            data = self._symbol_parser.get_symbol_data(
                ticker=self._ticker,
                strike=strike,
                expiry=expiry,
                option_type="CE"
            )
            if data is not None and "token" in data:
                option_tokens.append(data['token'])
                self._token_symbol_mapper[data['token']] = f"{self._ticker}{date_str}{strike}CE"

        for strike in pe_strikes or []:
            data = self._symbol_parser.get_symbol_data(
                ticker=self._ticker,
                strike=strike,
                expiry=expiry,
                option_type="PE"
            )
            if data is not None and "token" in data:
                option_tokens.append(data['token'])
                self._token_symbol_mapper[data['token']] = f"{self._ticker}{date_str}{strike}PE"
        return option_tokens

    @staticmethod
    def get_nearest_50_strike(index: float) -> int:
        """ Return the nearest 50 strike """
        return round(index / 50) * 50


if __name__ == "__main__":
    from src import BASE_DIR
    from src.utils.config_reader import ConfigReader
    config_path = BASE_DIR / 'data' / 'config.json'
    config = ConfigReader(config_file_path=config_path)
    market_feeds_accounts = config["market_feeds"]
    symbol_parser = AngelBrokingSymbolParser.instance()
    option_type = "CE"
    account = market_feeds_accounts[option_type]
    market_feeds = MarketFeeds(
        api_key=account["api_key"],
        client_id=account["client_id"],
        password=account["password"],
        totp_key=account["totp_key"],
        symbol_parser=symbol_parser,
        only_ce_or_pe=False
    )
    market_feeds.setup()

