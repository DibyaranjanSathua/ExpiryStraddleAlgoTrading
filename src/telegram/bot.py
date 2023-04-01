"""
File:           bot.py
Author:         Dibyaranjan Sathua
Created on:     01/04/23, 10:56 am
"""
import requests

from src.utils.config_reader import ConfigReader
from src.utils.logger import LogFacade

logger: LogFacade = LogFacade.get_logger("bot")


class Bot:
    """ Telegram bot to send notification """

    def __init__(self, config: ConfigReader):
        self._config: ConfigReader = config
        self._token: str = self._config["token"]
        self._chat_id: int = self._config["chat_id"]

    def send_notification(self, message: str):
        json_data = {
            "chat_id": self._chat_id,
            "text": message
        }
        try:
            response = requests.post(
                url=self.send_message_endpoint,
                json=json_data
            )
        except ConnectionError as err:
            logger.error(f"Error sending notification: {err}")
            return

        if not response.ok:
            logger.error(
                f"Error sending notification to {self.send_message_endpoint} "
                f"(HTTP {response.status_code}): {response.text}"
            )
            return
        json_response = response.json()
        if not json_response.get("ok", False):
            logger.error(
                f"Error sending notification to {self.send_message_endpoint} "
                f"(HTTP {response.status_code}): {json_response}"
            )
            return
        logger.info(json_response)

    @property
    def send_message_endpoint(self):
        """ Send message endpoint """
        return f"https://api.telegram.org/bot{self._token}/sendMessage"


if __name__ == "__main__":
    from src import BASE_DIR
    from src.utils.config_reader import ConfigReader

    config_path = BASE_DIR / 'data' / 'config.json'
    config = ConfigReader(config_file_path=config_path)
    telegram_config = config["telegram"]
    bot = Bot(config=telegram_config)
    bot.send_notification("Testing notification from SathuaLabs")
