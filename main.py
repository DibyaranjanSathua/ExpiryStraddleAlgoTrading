"""
File:           main.py
Author:         Dibyaranjan Sathua
Created on:     29/08/22, 1:31 am
"""
from typing import Optional
import argparse
import traceback

from src import BASE_DIR
from src.market_feeds.market_feeds import MarketFeeds
from src.strategies.strategy1 import Strategy1
from src.price_monitor.price_monitor import PriceMonitor
from src.brokerapi.angelbroking import AngelBrokingSymbolParser
from src.utils.redis_backend import RedisBackend
from src.utils.config_reader import ConfigReader
from src.utils.logger import LogFacade


config_path = BASE_DIR / 'data' / 'config.json'
config = ConfigReader(config_file_path=config_path)


def clean_up():
    """ Perform clean up tasks """
    # Connect to redis and clean up all nifty keys so that we don't end up using some old keys
    redis_backend = RedisBackend()
    redis_backend.connect()
    redis_backend.cleanup(pattern="NIFTY*")


def run_market_feed(market_feed_logger: LogFacade, option_type: Optional[str] = None):
    """ Run market feed """
    market_feeds_accounts = config["market_feeds"]
    symbol_parser = AngelBrokingSymbolParser.instance()
    if option_type is None:
        market_feed_logger.info(f"Setting up market feeds for both CE or PE strikes")
        account = market_feeds_accounts["CE"]
        market_feeds = MarketFeeds(
            api_key=account["api_key"],
            client_id=account["client_id"],
            password=account["password"],
            totp_key=account["totp_key"],
            symbol_parser=symbol_parser,
            only_ce_or_pe=False,
        )
        market_feeds.setup()
    else:
        market_feed_logger.info(f"Setting up market feeds for {option_type} strikes")
        account = market_feeds_accounts[option_type]
        market_feeds = MarketFeeds(
            api_key=account["api_key"],
            client_id=account["client_id"],
            password=account["password"],
            totp_key=account["totp_key"],
            symbol_parser=symbol_parser,
            only_ce_or_pe=True,
            option_type=option_type
        )
        market_feeds.setup()


def run_strategy1(logger: LogFacade, dry_run: bool):
    """ Run strategy1 """
    strategy_config = config["strategies"][Strategy1.STRATEGY_CODE]
    trading_accounts = config["trading_accounts"]
    price_monitor = PriceMonitor()
    price_monitor.setup()
    price_monitor.run_in_background()
    for account in trading_accounts:
        meta = account["meta"]
        if Strategy1.STRATEGY_CODE not in meta["strategies"]:
            logger.info(
                f"Skipping running {Strategy1.STRATEGY_CODE} for {meta['name']} as "
                f"{Strategy1.STRATEGY_CODE} is missing in meta['strategies']"
            )
            continue
        logger.info(
            f"Running {Strategy1.STRATEGY_CODE} for account {meta['name']} with client id "
            f"{account['client_id']}"
        )
        try:
            strategy = Strategy1(
                api_key=account["api_key"],
                client_id=account["client_id"],
                password=account["password"],
                totp_key=account["totp_key"],
                price_monitor=price_monitor,
                config=strategy_config,
                dry_run=dry_run
            )
            strategy.execute()
        except Exception as err:
            logger.error(
                f"Strategy1 execution error for {meta['name']} with client id "
                f"{account['client_id']}"
            )
            logger.error(err)
            logger.exception(traceback.print_exc())


def main():
    """ Main function """
    parser = argparse.ArgumentParser()
    parser.add_argument("--market-feeds", action="store_true")
    parser.add_argument("--trading", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--clean-up", action="store_true")
    parser.add_argument("--option-type", type=str, help="Use for market feeds to get strike data")
    args = parser.parse_args()
    if args.trading:
        trading_logger: LogFacade = LogFacade.get_logger("trading_main")
        try:
            run_strategy1(logger=trading_logger, dry_run=args.dry_run)
        except Exception as err:
            trading_logger.error(err)
            trading_logger.exception(traceback.print_exc())
    if args.market_feeds:
        if args.option_type == "CE":
            market_feed_logger: LogFacade = LogFacade.get_logger("ce_market_feed_main")
        else:
            market_feed_logger: LogFacade = LogFacade.get_logger("pe_market_feed_main")
        try:
            run_market_feed(market_feed_logger, args.option_type)
        except Exception as err:
            market_feed_logger.error(err)
            market_feed_logger.exception(traceback.print_exc())

    if args.clean_up:
        clean_up()


if __name__ == "__main__":
    main()
