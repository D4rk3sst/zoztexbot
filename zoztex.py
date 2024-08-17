import os
import sys
from termcolor import colored
import re
import json
from datetime import datetime, timedelta
import time
import logging
import asyncio
import datetime
from termcolor import colored
from telethon.sync import TelegramClient
from config.qtx_conf import qtx, qtx_email, qtx_pass, account, duration
from config.tele_conf import teleclient, phone_number, api_id, api_hash, channel_id
from zoztex import Quotex
from zoztex.utils import asset_parse, asrun
from zoztex.utils.operation_type import OperationType
from zoztex.exceptions import QuotexTimeout, QuotexAuthError
logger = logging.getLogger(__name__)


async def telegram_login():
    await teleclient.start(phone_number)

async def login():
    print(colored('[INFO]', 'blue'), "logging in ")
    try:
        while True:
            try:
                connect = await qtx.connect()
                if connect:
                    qtx.change_account(account)
                    return True
                else:
                    session_file = os.path.expanduser("./..sessions.pkl")
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
    LAST_MESSAGE_ID_FILE = 'last_message_id.txt'
    SIGNALS_JSON_FILE = 'signals.json'
    try:
        with open(LAST_MESSAGE_ID_FILE, 'r') as f:
            last_message_id = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        last_message_id = 0

    while True:
        valid_signal_found = False  # Initialize at the start of each iteration

        entity = await teleclient.get_entity(channel_id)
        new_messages = await teleclient.get_messages(entity, min_id=last_message_id)

        max_id = last_message_id
        new_signals = []

        for message in new_messages:
            if message.id > last_message_id and message.text:
                signal_lines = message.text.split('\n')

                # Check if the message starts with the clock emoji (⏰)
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

                        # Print signal received message
                        print(colored('SIGNAL RECEIVED', 'yellow'))
                        print(colored("Direction:", 'magenta'), direction)
                        print(colored('--------------', 'green'))

                        valid_signal_found = True
                        max_id = max(max_id, message.id)

                        # Save new signals to signals.json (overwrite mode)
                        with open(SIGNALS_JSON_FILE, 'w') as json_file:
                            json.dump(new_signals, json_file, indent=4)

                        # Save the last processed message ID after processing
                        last_message_id = max_id
                        with open(LAST_MESSAGE_ID_FILE, 'w') as f:
                            f.write(str(last_message_id))

                        return data  # Return the valid signal data

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

async def trade(direction, asset):
    if await con_stat():
        status, trade_info = await qtx.trade(direction, amount, asset, duration)
        if status:
            print("Trade opened successfull")
        else:
            print('trade unsuccessfull')
    else:
        print('connection problem')
    return status, trade_info


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
        print(i)
        while time.time() - start_time < i:
            pass

async def execute(asset, direction):
    print(asset)

async def allinone(signal_data):
    await login()
    print('Initializing trade')
    balance = await qtx.get_balance()
    trade_time = signal_data.get('Time to Execute')
    asset = signal_data.get('Currency Pair').replace('/', '')
    direction = signal_data.get('Direction')
    if direction == 'PUT':
        direction = OperationType.PUT_RED
    elif direction == 'BUY':
        direction = OperationType.CALL_GREEN
    asset, asset_open = check_asset(asset)
    amount = int(balance) * 0.04
    amount_gale = int(balance) * 0.08
    print(f"Trade amount: {amount}  Gale amount: {amount_gale}      Balance: {balance}")
    hours, minutes = map(int, trade_time.split(':'))
    target_time = datetime.datetime.combine(datetime.date.today(), datetime.time(hours, minutes, 0))
    print(colored('[Waiting]', 'white'), f" {trade_time}")
    while True:
        current_time = datetime.datetime.now()
        if current_time.hour == target_time.hour and current_time.minute == target_time.minute:
            break
    print("executing now")
    count(3)
    await con_stat()
    print('logged in')
    stat, info = await qtx.trade(direction, amount, asset, duration)
    print('trade opened')
    print(stat)
    if stat:
        print('trade opened, checking win now')
        win = await qtx.check_win(info['id'])
        if win:
            print(colored('winn', 'green'))
        else:
            await con_stat()
            loss = await qtx.check_win(info['id'])
            if loss:
                print(colored('WIN', 'green'), "Profit: ",  qtx.get_profit())
            else:
                print(colored('Loss', 'red'))
                gale, gale_info = await qtx.trade(direction, amount_gale, asset, duration)
                if gale:
                    print('gale executed')
                    gale_check = await qtx.check_win(gale_info['id'])
                    print(gale_check)
                    if gale_check:
                        print(colored('Gale Win', 'green'), 'Profit: ',  qtx.get_profit())
                    else:
                        print(colored('loss', 'red'))
    else:
        print(colored('[ERROR]', 'red'), 'trade not executed')
    print("Balance:  ", await qtx.get_balance())
                        



async def main():
    await telegram_login()
    while True:
        print("waiting signal")
        signal = await signals()
        await allinone(signal)
        qtx.close()
    '''
    conn = qtx.is_connected
    print(conn)
    log = await login()
    print(log)
    await con_stat()
    direction = OperationType.PUT_RED
    asset = 'USDINR'
    asset, asset_open = check_asset(asset)
    if asset_open:
        stat, trade_info = await trade(direction, asset)
        if stat:
            print(trade_info['id'])
            if await qtx.check_win(trade_info['id']):
                print('win')
            else:
                print('loss')
                print('checking again')
                count(3)
                if await qtx.check_win(trade_info['id']):
                    print('win, shitty api')
                else:
                    print('real loss')
        else:
            print('trade not opened')
    '''

    '''for i in range(20):
        logger.info('Are u still connected ??')
    stat, tradess = await qtx.trade(OperationType.PUT_RED, 3, 'USDMXN_otc', 20)
    if stat:
        print('trade opened')
        if await qtx.check_win(tradess['id']):
            print('win')
        else:
            print('loss, double checking now')
            count(3)
            try:
                qtx.close()
                await con_stat()
                if await qtx.check_win(tradess['id']):
                    print('win,  shiity api')
                else:    
                    print('loss')
            except asyncio.TimeoutError:
                print('timout')
                qtx.close()
                await login()
                if await qtx.check_win(tradess['id']):
                    print('win')
                else:
                    print('loss')

            print('tryin 5 min now')
    stat, trades = await qtx.trade(OperationType.CALL_GREEN, 3, 'USDMXN_otc', 300)
    if stat:
        print('trade opened')
        if await qtx.check_win(trades['id']):
            print('win')
        else:
            print('loss, double checking now')
            if await qtx.check_win(trades['id']):
                print('win, shitty api')
            else:
                print('real loss')
    print('done successfull ur insane zz')
'''
if __name__ == "__main__":
    try:
        asrun(main())
    except KeyboardInterrupt:
        qtx.close()
        print('hotkey shutdown')
    