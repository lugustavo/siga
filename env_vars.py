"""
EnvironmentVariables: A class to load Environment Variables configurations and validate them against.
Imports:
- os: Operating system interface (OS routines for NT or Posix depending on what system we're on)
- logging: Logging facility for Python.
- dotenv: Load environment variables from .env file

Example usage:
# Create an instance of the EnvironmentVariables class
env_vars = EnvironmentVariables()

# Validate environment variables
if env_vars.validate():
    # Example usage
    logger.info("BOT_TOKEN: %s", env_vars.bot_token)
    logger.info("BOT_CHAT_ID: %s", env_vars.bot_chat_id)
else:
    logger.error("Please set the required environment variables and try again.")
"""
import os
import logging
from dotenv import load_dotenv

# Configure logging
# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnvironmentVariables:
    """
    A class to manage environment variables related to a bot.
    Attributes:
        bot_token (str): The bot token.
        bot_chat_id (str): The chat ID of the bot.
    """
    def __init__(self):
        """
        Initialize the EnvironmentVariables object and load environment variables.
        """
        load_dotenv(override=True)
        self.bot_token = os.getenv("BOT_TOKEN")
        self.bot_chat_id = os.getenv("BOT_CHAT_ID")

    def validate(self):
        """
        Validate if the required environment variables are set.
        Returns:
            bool: True if all required environment variables are set, False otherwise.
        """
        if not self.bot_token or not self.bot_chat_id:
            logger.info("Environment variables BOT_TOKEN and BOT_CHAT_ID for Telegram not found")
            return False

        logger.info("Found env variables")
        logger.info("BOT_TOKEN: %s", self.bot_token)
        logger.info("BOT_CHAT_ID: %s", self.bot_chat_id)
        return True