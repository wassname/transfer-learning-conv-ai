import os
import random
import slack
import coloredlogs
import time
import json
import zmq
import collections
import logging
import datetime
import sys

# For api token https://github.com/slackapi/python-slackclient/blob/master/tutorial/01-creating-the-slack-app.md
# need rights channels:read channels:history incoming-webhook  chat:write:bot 
# you also need to add the bot to the channel!

# Logging
ts = datetime.datetime.utcnow().strftime('%Y%m%d_%H-%M-%S')
logging.basicConfig(
    level=logging.INFO, 
    format='[{%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(filename=f'slack_bot_{ts}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__file__)
coloredlogs.install(level=logging.DEBUG)

logging.getLogger("zmqtest").setLevel(logging.DEBUG)

secrets = json.load(open(".secrets.json"))
slack_token = secrets["slack"]["Bot User OAuth Access Token"]


class ModelAPI(object):
    def __init__(self):

        # Zeromq to pytorch server
        port = "5586"
        logger.info(f"Joining Zeromq server in {port}")
        context = zmq.Context()
        self.socket = context.socket(zmq.PAIR)
        self.socket.connect("tcp://localhost:%s" % port)
        time.sleep(1)
        server_config = self.socket.recv_json()
        logger.info("Connected to server, received initial message: %s", server_config)
        self.history = collections.defaultdict(list)

    def gen_roast(self, reply, name):
        # return '$ROAST'
        self.history[name].append(reply)
        personality = random.choice(['RoastMe', 'totallynotrobots', 'dreams'])
        payload = dict(personality=personality, history=self.history[name])
        logger.debug("payload %s", payload)
        self.socket.send_json(payload)

        reply = self.socket.recv_json()["data"]
        self.history[name].append(reply)
        return reply


model_api = ModelAPI()
# TODO channel whitelist, only roast people who invite it or speak in a thread
@slack.RTMClient.run_on(event='message')
def say_hello(**payload):
    print('message', payload)
    data = payload['data']
    web_client = payload['web_client']
    rtm_client = payload['rtm_client']
    channel_id = data['channel']
    thread_ts = data['ts']
    if 'text' in data and 'user' in data and not 'subtype' in data:
        body = data['text']
        name = data['user']
        msg = model_api.gen_roast(body, name)
        web_client.chat_postMessage(
            channel=channel_id,
            text=msg,
            thread_ts=thread_ts
        )
        logger.info("Out msg %s", dict(channel=channel_id,
            text=msg,
            thread_ts=thread_ts))
        # 'subtype': 'bot_message', 
        # 'subtype': 'message_replied'
        # 'subtype': 'channel_purpose'

# Initial message wit hwebclient
client = slack.WebClient(token=slack_token)
response = client.chat_postMessage(
    channel='#roastme_robot',
    text="I'm online! I'm a badly behaved robot. Roast me puny humans; and I will roast you back.")

logger.info("Starting RTMClient")
rtm_client = slack.RTMClient(token=slack_token)
rtm_client.start()
