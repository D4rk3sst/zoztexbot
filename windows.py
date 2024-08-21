import os
import sys
import re
import json
from datetime import datetime, timedelta
import time
import logging
import asyncio
from termcolor import colored
from telethon.sync import TelegramClient
from config.qtx_conf import qtx, qtx_email, qtx_pass, account, duration
from config.tele_conf import teleclient, phone_number, api_id, api_hash, channel_id
from quotexpy import Quotex
from quotexpy.utils import asset_parse, asrun
from quotexpy.utils.operation_type import OperationType
from quotexpy.exceptions import QuotexTimeout, QuotexAuthError

logger = logging.getLogger(__name__)

qtx.debug_ws = True

async def telegram_login():
    await teleclient.start(phone_number)

async def login():
    print(colored('[INFO]', 'blue'), "logging in")
    try:
        while True:
            try:
                connect = await qtx.connect()
                if connect:
                    qtx.change_account(account)
                    return True
                else:
                    session_file = os.path.expanduser("~/.sessions/sessions.pkl")
                    if os.path.exists(session_file):
                        os.remove(session_file)
            except QuotexTimeout:
                print('Taking more than usual')
            except QuotexAuthError:
                await asyncio.sleep(2)
    except Exception as e:
        print(e, "error in login")
        await login()

async def signals():
    LAST_MESSAGE_ID_FILE = os.path.expanduser("~/.sessions/last_message_id.txt")
    SIGNALS_JSON_FILE = os.path.expanduser("~/.sessions/signals.json")
    try:
        with open(LAST_MESSAGE_ID_FILE, 'r') as f:
            last_message_id = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        last_message_id = 0

    while True:
        valid_signal_found = False

        entity = await teleclient.get_entity(channel_id)
        new_messages = await teleclient.get_messages(entity, min_id=last_message_id)

        max_id = last_message_id
        new_signals = []

        for message in new_messages:
            if message.id > last_message_id and message.text:
                signal_lines = message.text.split('\n')

                if signal_lines and signal_lines[0].startswith('⏰'):
                    time_zone = expiry = currency_pair = time_to_execute = direction = first_gale_time = None
                    contains_info = False

                    for line in signal_lines:
                        if line.startswith('⏰'):
                            time_zone = line.split(':')[-1].strip()
                            contains_info = True
                        elif line.startswith('💰'):
                            expiry = line.split()[-2]
                            contains_info = True
                        elif '/' in line:
                            match = re.search(r'([\w/]+);(\d{2}:\d{2});(PUT|BUY)', line)
                            if match:
                                currency_pair, time_to_execute, direction = match.groups()
                                contains_info = True
                        elif 'GALE' in line:
                            match = re.search(r'\d{2}:\d{2}', line)
                            if match:
                                first_gale_time = match.group()
                                contains_info = True

                    if contains_info:
                        data = {
                            "Currency Pair": currency_pair,
                            "Time to Execute": time_to_execute,
                            "Direction": direction,
                            "Time Zone": time_zone,
                            "Expiry": expiry,
                            "First Gale Time": first_gale_time
                        }

                        new_signals.append(data)

                        print(colored('SIGNAL RECEIVED', 'yellow'))
                        print(colored("Direction:", 'magenta'), direction)
                        print(colored('--------------', 'green'))

                        valid_signal_found = True
                        max_id = max(max_id, message.id)

                        with open(SIGNALS_JSON_FILE, 'w') as json_file:
                            json.dump(new_signals, json_file, indent=4)

                        last_message_id = max_id
                        with open(LAST_MESSAGE_ID_FILE, 'w') as f:
                            f.write(str(last_message_id))

                        return data

        await asyncio.sleep(5)

def check_asset(asset):
    asset_query = asset_parse(asset)
    asset_open = qtx.check_asset(asset_query)
    print(asset_open)
    if not asset_open or not asset_open[2]:
        print(colored("[WARN]: ", "yellow"), "Asset is closed.")
        asset = f"{asset}_otc"
        print(colored("[WARN]: ", "yellow"), "Try OTC Asset -> " + asset)
        asset_query = asset_parse(asset)
        asset_open = qtx.check_asset(asset_query)
        if not asset_open or not asset_open[2]:
            print(f"{asset} market closed")
        else:
            print(asset_open[2])
    return asset, asset_open

async def con_stat():
    while True:
        connection = qtx.is_connected
        if not connection:
            await login()
        if connection:
            return connection

def count(sec):
    start_time = time.time()
    for i in range(1, sec):
        while time.time() - start_time < i:
            pass

def load_state(file_path):
    try:
        with open(file_path, 'r') as file:
            state = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        state = {"loss_count": 0, "consecutive_wins": 0}
    return state

def save_state(file_name, state):
    with open(file_name, 'w') as f:
        json.dump(state, f)

async def allinone(signal_data):
    print('Initializing trade')
    trade_time = signal_data.get('Time to Execute')
    asset = signal_data.get('Currency Pair').replace('/', '')
    direction = signal_data.get('Direction')

    if direction == 'PUT':
        direction = OperationType.PUT
    elif direction == 'BUY':
        direction = OperationType.CALL

    await con_stat()
    asset, asset_open = check_asset(asset)

    balance = await qtx.get_balance()
    amount = int(balance) * 0.024
    gale_amount = int(balance) * 0.0441
    if int(amount) < 1:
        amount = 1
    if int(gale_amount) < 1:
        gale_amount = 1.6
    print(f"Trade amount: {amount}  Gale amount: {gale_amount}  Balance: {balance}")
    qtx.close()

    hours, minutes = map(int, trade_time.split(':'))
    target_time = datetime.combine(datetime.date.today(), datetime.time(hours, minutes, 0))
    print(colored('[Waiting]', 'white'), f" {trade_time}")
    adjusted_time = target_time - timedelta(seconds=15)

    while True:
        current_time = datetime.now()
        if current_time >= adjusted_time:
            break

    qtx.debug_ws = True
    await login()
    print('logged in')
    count(10)
    stat, info = await qtx.trade(direction, amount, asset, duration)
    if stat:
        print("Trade Executed, checking win")
        win = await qtx.check_win(info.id)
        if win:
            print(colored('WIN', 'green'), "PROFIT: ", qtx.get_profit())
        else:
            await con_stat()
            checkwin = await qtx.check_win(info.id)
            if checkwin:
                print(colored('WIN', 'green'), "PROFIT: ", qtx.get_profit())
            else:
                print(colored('LOSS', 'red'))
                gale, gale_info = await qtx.trade(direction, gale_amount, asset, duration)
                if gale:
                    print("Gale executed, checking win")
                    gale_win = await qtx.check_win(gale_info.id)
                    if gale_win:
                        print(colored('WIN', 'green'), "PROFIT: ", qtx.get_profit())
                    else:
                        await con_stat()
                        galecheckwin = await qtx.check_win(gale_info.id)
                        if galecheckwin:
                            print(colored('WIN', 'green'), "PROFIT: ", qtx.get_profit())
                        else:
                            print(colored('LOSS', 'red'))
    else:
        print('trade not executed, check amounts')

async def main():
    while True:
        await telegram_login()
        print("waiting signal")
        signal = await signals()
        await allinone(signal)

if __name__ == "__main__":
    try:
        asrun(main())
    except KeyboardInterrupt:
        print("aborted")
        sys.exit(0)
