from typing import Any, List, Tuple
import math

from telegram import Bot, Update
from telegram.ext import CallbackContext, Filters, MessageHandler, Updater


class MainRunnerConfig:
    def __init__(self, token: str, super_admin: int, conversion_rate: float, dec_limit: int):
        self.token = token
        self.super_admin = super_admin
        self.conversion_rate = conversion_rate
        self.dec_limit = dec_limit


class TrcNetConfig:
    def __init__(self, full_node_api: str, solidity_api: str, default_account: str, private_key: str):
        self.full_node_api = full_node_api
        self.solidity_api = solidity_api
        self.default_account = default_account
        self.private_key = private_key


def parse_command(text: str) -> Tuple[str, List[str]]:
    parts = text.split(" ", 1)
    if len(parts) == 1:
        return parts[0], []
    return parts[0], parts[1].split()


def send_welcome_message(bot: Bot, chat_id: int) -> None:
    message = "Welcome to our bot!\n\nUse /sendusdt command to send USDT to a specified address and receive the corresponding TRX.\n\nUse /setrate command to set the exchange rate between USDT and TRX."
    bot.send_message(chat_id=chat_id, text=message)


def send_unknown_command_message(bot: Bot, chat_id: int) -> None:
    message = "Unknown command. Use /start command to see available commands."
    bot.send_message(chat_id=chat_id, text=message)


def set_exchange_rate(bot: Bot, chat_id: int, super_admin: int, args: List[str], bot_config: MainRunnerConfig) -> None:
    if chat_id != super_admin:
        bot.send_message(chat_id=chat_id, text="Not logged in as Admin.")
        return

    if len(args) != 1:
        bot.send_message(chat_id=chat_id, text="Invalid command format. Use /setrate rate to set the exchange rate")
        return

    try:
        rate = float(args[0])
    except ValueError:
        bot.send_message(chat_id=chat_id, text="Exchange rate must be a number.")
        return

    bot_config.conversion_rate = rate
    bot.send_message(chat_id=chat_id, text=f"Exchange rate between USDT and TRX has been updated to {rate}.")

def send_usdt(bot: Bot, chat_id: int, tron_api: Any, args: List[str], bot_config: MainRunnerConfig, tron_config: TrcNetConfig) -> None:
    if len(args) != 2:
        bot.send_message(chat_id=chat_id, text="Invalid command format. Use /sendusdt address amount to send USDT to the specified address, where address is the TRC20 address and amount is the amount of USDT.")
        return

    address, amount_str = args
    try:
        amount = float(amount_str)
    except ValueError:
        bot.send_message(chat_id=chat_id, text="Amount must be a number.")
        return

    trx_amount = math.floor(amount * bot_config.conversion_rate * 10 ** bot_config.dec_limit) / 10 ** bot_config.dec_limit

    if trx_amount > bot_config.max_trx_to_send:
        bot.send_message(chat_id=chat_id, text=f"Can only send up to {bot_config.max_trx_to_send} TRX at a time.")
        return

    if not tron_api.validate_address(tron_config.full_node_api, address):
        bot.send_message(chat_id=chat_id, text="Invalid TRC20 address.")
        return

    contract_address = tron_api.to_hex_address(tron_config.default_account)

    usdt = tron_api.get_trc20_interface(contract_address)
    if usdt is None:
        bot.send_message(chat_id=chat_id, text="Failed to get TRC20 interface.")
        return

    try:
        decimals = usdt.decimals()
    except Exception:
        bot.send_message(chat_id=chat_id, text="Failed to get USDT decimals.")
        return

    amount_int = int(amount * 10 ** decimals)

    try:
        balance = usdt.balance_of(address)
    except Exception:
        bot.send_message(chat_id=chat_id, text="Failed to get user's USDT balance.")
        return

    if balance < amount_int:
        bot.send_message(chat_id=chat_id, text="Insufficient USDT balance.")
        return

    try:
        tx = usdt.transfer(address, amount_int)
    except Exception:
        bot.send_message(chat_id=chat_id, text="Failed to send USDT.")
        return

    try:
        receipt = tron_api.wait_for_transaction_receipt(tx['txid'])
    except Exception:
        bot.send_message(chat_id=chat_id, text="Failed to confirm USDT transaction.")
        return

    try:
        trx_tx = tron_api.transfer(tron_config.default_account, bot_config.super_admin, trx_amount)
    except Exception:
        bot.send_message(chat_id=chat_id, text="Failed to send TRX.")
        return

    try:
        trx_receipt = tron_api.wait_for_transaction_receipt(trx_tx['txid'])
    except Exception:
        bot.send_message(chat_id=chat_id, text="Failed to confirm TRX transaction.")
        return

    message = f"USDT transaction successful. {amount} USDT sent to address {address}. TRX transaction successful. {trx_amount} TRX sent to address {bot_config.super_admin}."
    bot.send_message(chat_id=chat_id, text=message)


def handle_message(update: Update, context: CallbackContext) -> None:
    if update.message is None:
        return

    command, args = parse_command(update.message.text)

    if command == "/start":
        send_welcome_message(context.bot, update.message.chat_id)
    elif command == "/setrate":
        set_exchange_rate(context.bot, update.message.chat_id, bot_config.super_admin, args, bot_config)
    elif command == "/sendusdt":
        send_usdt(context.bot, update.message.chat_id, tron_api, args, bot_config, tron_config)
    else:
        send_unknown_command_message(context.bot, update.message.chat_id)


if __name__ == "__main__":
    bot_config = MainRunnerConfig(
        token="YOUR_TELEGRAM_BOT_TOKEN",  # Replace with your Telegram Bot token
        super_admin=YOUR_TELEGRAM_CHAT_ID,  # Replace with your Telegram Chat ID
        conversion_rate=40,
        dec_limit=3
    )
    tron_config = TrcNetConfig(
        full_node_api="https://api.trongrid.io",
        solidity_api="https://api.trongrid.io",
        default_account="YOUR_TRON_ACCOUNT_ADDRESS",  # Replace with your Tron account address
        private_key="YOUR_TRON_ACCOUNT_PRIVATE_KEY"  # Replace with your Tron account private key
    )

    updater = Updater(token=bot_config.token, use_context=True)
    updater.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    updater.idle()
