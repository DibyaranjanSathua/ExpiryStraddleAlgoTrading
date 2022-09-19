"""
File:           main.py
Author:         Dibyaranjan Sathua
Created on:     29/08/22, 1:31 am
"""
import argparse
import traceback
import threading

from src import BASE_DIR
from src.market_feeds.market_feeds import MarketFeeds
from src.strategies.strategy1 import Strategy1
from src.price_monitor.price_monitor import PriceMonitor
from src.brokerapi.angelbroking import AngelBrokingSymbolParser
from src.utils.config_reader import ConfigReader
from src.utils.logger import LogFacade


trading_logger: LogFacade = LogFacade.get_logger("trading_main")
market_feed_logger: LogFacade = LogFacade.get_logger("market_feed_main")
config_path = BASE_DIR / 'data' / 'config.json'
config = ConfigReader(config_file_path=config_path)


def run_market_feed():
    """ Run market feed """
    market_feeds_accounts = config["market_feeds"]["accounts"]
    symbol_parser = AngelBrokingSymbolParser.instance()
    if len(market_feeds_accounts) > 1:
        market_feed_logger.info(f"Setting up market feeds for CE strikes")
        account = market_feeds_accounts.pop()
        market_feeds = MarketFeeds(
            api_key=account["api_key"],
            client_id=account["client_id"],
            password=account["password"],
            symbol_parser=symbol_parser,
            only_ce_or_pe=True,
            option_type="CE"
        )
        threading.Thread(target=market_feeds.setup).start()
        market_feed_logger.info(f"Setting up market feeds for PE strikes")
        account = market_feeds_accounts.pop()
        market_feeds = MarketFeeds(
            api_key=account["api_key"],
            client_id=account["client_id"],
            password=account["password"],
            symbol_parser=symbol_parser,
            only_ce_or_pe=True,
            option_type="PE"
        )
        threading.Thread(target=market_feeds.setup).start()
    else:
        market_feed_logger.info(f"Setting up market feeds for both CE or PE strikes")
        account = market_feeds_accounts.pop()
        market_feeds = MarketFeeds(
            api_key=account["api_key"],
            client_id=account["client_id"],
            password=account["password"],
            symbol_parser=symbol_parser,
            only_ce_or_pe=False,
        )
        market_feeds.setup()


def run_strategy1(dry_run: bool):
    """ Run strategy1 """
    strategy_config = config["strategies"][Strategy1.STRATEGY_CODE]
    price_monitor = PriceMonitor()
    price_monitor.setup()
    price_monitor.run_in_background()
    strategy = Strategy1(price_monitor=price_monitor, config=strategy_config, dry_run=dry_run)
    strategy.execute()


def main():
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("--market-feeds", action="store_true")
    parser.add_argument("--trading", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--clean-up", action="store_true")
    args = parser.parse_args()
    if args.trading:
        try:
            run_strategy1(dry_run=args.dry_run)
        except Exception as err:
            trading_logger.error(err)
            trading_logger.exception(traceback.print_exc())
    if args.market_feeds:
        try:
            run_market_feed()
        except Exception as err:
            market_feed_logger.error(err)
            market_feed_logger.exception(traceback.print_exc())


if __name__ == "__main__":
    main()
