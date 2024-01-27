# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=import-error
# pylint: disable=line-too-long

#!/usr/bin/env python3

import time
import threading
import datetime
import logging
import argparse
import random
from mfrc522 import MFRC522
import config_constants as const
from mqtt_clients import Client, SecretClient
import server_functions as sf
from terminal_colors import TerminalColors

class TokenData():
    def __init__(self):
        self.token = -1
        self.prev_token = -1
        self.token_change_timestamp = time.time()-const.GENERATE_TOKEN_PERIOD

    def check_token(self, token_str):
        current_timestamp = time.time()
        if current_timestamp - self.token_change_timestamp < const.TOKEN_CHANGE_COOLDOWN:
            return token_str == str(self.token) or token_str == str(self.prev_token)
        return token_str == str(self.token)

    def update_token(self):
        self.prev_token = self.token
        self.token = random.randint(0,99)
        self.token_change_timestamp = time.time()
        timestamp_iso = datetime.datetime.fromtimestamp(self.token_change_timestamp).strftime(const.ISO8601)
        LOGGER.info('%sGenerated new token at %s:%s %s  --->  %s%s', TerminalColors.YELLOW, timestamp_iso, TerminalColors.RED, self.prev_token, self.token, TerminalColors.RESET)

PARSER = argparse.ArgumentParser(description='Program for the RFiD card presence system administrator')
TOKEN_DATA = TokenData()
EXIT_EVENT = threading.Event()
LOGGER = logging.getLogger(__name__)

client_main = Client(
    broker=const.SERVER_BROKER,
    publisher_topics_list=[const.MAIN_TOPIC_CHECK_RESPONSE, const.MAIN_TOKEN_CHECK_RESPONSE],
    subscribers_topic_to_func_dict={
        const.MAIN_TOPIC_ADD : sf.add_card_to_trusted_main,
        const.MAIN_TOPIC_CHECK_REQUEST : sf.check_card_request_main,
        const.MAIN_TOKEN_CHECK_REQUEST : sf.check_rfid_token_main
    },
    variables={}
)

client_secret_1 = SecretClient(
    client_id=1,
    broker=const.SERVER_BROKER,
    publisher_topics_list=[const.SECRET_TOPIC_CHECK_RESPONSE, const.SECRET_TOKEN_CHECK_RESPONSE],
    subscribers_topic_to_func_dict={
        const.SECRET_TOPIC_ADD : sf.add_card_to_trusted_secret,
        const.SECRET_TOPIC_CHECK_REQUEST : sf.check_card_request_secret,
        const.SECRET_TOKEN_CHECK_REQUEST : sf.check_rfid_token_secret
    },
    variables={}
)

mqtt_clients = [client_main, client_secret_1]

def generate_tokens():
    while not EXIT_EVENT.is_set():
        time_now = time.time()
        if time_now - TOKEN_DATA.token_change_timestamp >= const.GENERATE_TOKEN_PERIOD:
            TOKEN_DATA.update_token()

def check_token(token_str):
    return TOKEN_DATA.check_token(token_str)

def config_parser():
    PARSER.add_argument('-r', '--reader', help='Specify the card reader')
    PARSER.add_argument('-lh', '--list-history', action='store_true', help='Print card presence history from the specified reader')
    PARSER.add_argument('-t', '--token', action='store_true', help='Print the current token')
    PARSER.add_argument('--exit', action='store_true', help='Terminate this program')
    PARSER.add_argument('-d', '--debug', action="store_true", help="Set the logging level to DEBUG")
    PARSER.add_argument('-i', '--info', action="store_true", help="Set the logging level to INFO")
    PARSER.add_argument('-w', '--warning', action="store_true", help="Set the logging level to WARNING")
    PARSER.add_argument('-e', '--error', action="store_true", help="Set the logging level to ERROR")
    PARSER.add_argument('-c', '--critical', action="store_true", help="Set the logging level to CRITICAL")

def connect_mqtts():
    for client in mqtt_clients:
        client.connect_publishers()
        client.connect_subscribers()

def disconnect_mqtts():
    for client in mqtt_clients:
        client.disconnect_publishers()
        client.disconnect_subscribers()

def run_server():
    logging.basicConfig(format='%(levelname)s:\t%(message)s', level=logging.INFO)
    config_parser()
    connect_mqtts()

    program_exit_flag = False

    token_thread = threading.Thread(target=generate_tokens)
    token_thread.start()

    while not program_exit_flag:
        arguments = input('Command: ')
        args, unknown = PARSER.parse_known_args(arguments.split())
        if args.list_history:
            print('History print required!')
        elif args.token:
            token_change_datetime = datetime.datetime.fromtimestamp(TOKEN_DATA.token_change_timestamp).strftime(const.ISO8601)
            print(f'Token [{token_change_datetime}]:\t{TOKEN_DATA.token}')
        elif args.debug:
            LOGGER.setLevel(level=logging.DEBUG)
        elif args.info:
            LOGGER.setLevel(level=logging.INFO)
        elif args.warning:
            LOGGER.setLevel(level=logging.WARNING)
        elif args.error:
            LOGGER.setLevel(level=logging.ERROR)
        elif args.critical:
            LOGGER.setLevel(level=logging.CRITICAL)
        elif args.exit:
            print('Terminating the program...')
            program_exit_flag = True
        else:
            print(f'Unknown commands: {unknown}')
    EXIT_EVENT.set()
    token_thread.join()
    disconnect_mqtts()


if __name__ == "__main__":
    run_server()
    print('----------------------------------')
    print('FINISHED')
