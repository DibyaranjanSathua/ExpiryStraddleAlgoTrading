"""
File:           market_feeds.py
Author:         Dibyaranjan Sathua
Created on:     09/08/22, 8:32 pm
"""
from typing import List, Optional
import datetime

from src.brokerapi.angelbroking import AngelBrokingApi, AngelBrokingSymbolParser, \
    TokenSymbolMapper


class MarketFeeds:
    """ Store the live market feeds in redis db """
    def __init__(self, api_key: str, client_id: str, password: str):
        self._api_key = api_key
        self._client_id = client_id
        self._password = password
        self._api = AngelBrokingApi(api_key=api_key, client_id=client_id, password=password)
        self._symbol_parser: Optional[AngelBrokingSymbolParser] = None
        self._option_tokens = []        # Stores the token for subscribing for web socket data
        self._token_symbol_mapper = TokenSymbolMapper()

    def setup(self):
        """ Setup required data for live market feeds """
        self._api.login()
        # Just to check if login is successful, fetch user profile
        self._api.get_user_profile()
        self._symbol_parser = AngelBrokingSymbolParser.instance()
        # Get the nifty ltp to determine the ATM price
        data = self._api.get_ltp_data(
            trading_symbol="NIFTY",
            symbol_token=self._symbol_parser.nifty_index_token,
            exhange="NSE"
        )
        # Added nifty index to token to symbol mapper
        self._token_symbol_mapper[self._symbol_parser.nifty_index_token] = "NIFTY"
        nifty_index = data["ltp"]
        atm = self.get_nearest_50_strike(nifty_index)
        ce_strikes = [atm + (50 * x) for x in range(15)]    # 15 CE strikes (ATM + OTM)
        ce_strikes += [atm - (50 * x) for x in range(1, 10)]  # 10 CE strikes ITM
        pe_strikes = [atm - (50 * x) for x in range(15)]    # 15 PE strikes (ATM + OTM)
        pe_strikes += [atm + (50 * x) for x in range(1, 10)]    # 10 PE strikes ITM
        # Get the current expiry
        current_expiry = self._symbol_parser.current_week_expiry
        self._option_tokens = self.get_option_tokens(
            ce_strikes=ce_strikes, pe_strikes=pe_strikes, expiry=current_expiry
        )
        # Setup market feed
        self._api.setup_market_feeds()
        self._api.market_feeds.options_tokens = self._option_tokens
        self._api.market_feeds.index_tokens = [self._symbol_parser.nifty_index_token]
        self._api.market_feeds.connect()

    def get_option_tokens(self, ce_strikes: List, pe_strikes: List, expiry: datetime.date):
        """ Get the option tokens for ce_strikes and pe_strikes """
        option_tokens = []
        date_str = expiry.strftime("%d%b%y").upper()
        for strike in ce_strikes:
            data = self._symbol_parser.get_symbol_data(
                ticker="NIFTY",
                strike=strike,
                expiry=expiry,
                option_type="CE"
            )
            if "token" in data:
                option_tokens.append(data['token'])
                self._token_symbol_mapper[data['token']] = f"NIFTY{date_str}{strike}CE"

        for strike in pe_strikes:
            data = self._symbol_parser.get_symbol_data(
                ticker="NIFTY",
                strike=strike,
                expiry=expiry,
                option_type="PE"
            )
            if "token" in data:
                option_tokens.append(data['token'])
                self._token_symbol_mapper[data['token']] = f"NIFTY{date_str}{strike}PE"
        return option_tokens

    @staticmethod
    def get_nearest_50_strike(index: float) -> int:
        """ Return the nearest 50 strike """
        return round(index / 50) * 50


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from src import BASE_DIR
    dotenv_path = BASE_DIR / 'env' / '.env'
    load_dotenv(dotenv_path=dotenv_path)
    api_key = os.environ.get("ANGEL_BROKING_API_KEY")
    client_id = os.environ.get("ANGEL_BROKING_CLIENT_ID")
    password = os.environ.get("ANGEL_BROKING_PASSWORD")
    market_feeds = MarketFeeds(api_key=api_key, client_id=client_id, password=password)
    market_feeds.setup()

