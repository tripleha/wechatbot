#!/usr/bin/env python
# coding: utf-8

#===================================================
from wechat.utils import *
from config import Constant
#---------------------------------------------------
import random, time, json
import grequests
#===================================================


class Bot(object):

    def __init__(self):
        self.emoticons = Constant.EMOTICON
        self.gifs = []
        self.last_time = time.time()

        self.tuling_session = requests.session()
        # 可以添加更多bot对话

    def close_session(self):
        self.tuling_session.close()

    def tuling_reply(self, text, user_id):
        api_key = Constant.BOT_TULING_API_KEY
        api_url = Constant.BOT_TULING_API_URL % (api_key, text, user_id)
        r = json.loads(get(self.tuling_session, api_url))
        if r.get('code') == 100000 and r.get('text') != Constant.BOT_TULING_BOT_REPLY:
            return r['text']
        return ''

    def get_many_reply(self, need_reply_list):
        def except_handler():
            echo('request bot reply failed\n')

        api_key = Constant.BOT_TULING_API_KEY
        api_urls = [Constant.BOT_TULING_API_URL % (api_key, ne_reply['text'], ne_reply['user'])
                    for ne_reply in need_reply_list]
        reqs = [grequests.get(url) for url in api_urls]
        responses = grequests.map(reqs, exception_handler=except_handler)
        rs = map(lambda r: json.loads(r.content) if r else None, responses)
        result = []
        for rg in rs:
            if rg:
                if rg.get('code') == 100000 and rg.get('text'):
                    result.append(trans_coding(rg['text']))
                else:
                    result.append(Constant.BOT_TULING_BOT_REPLY)
            else:
                result.append(Constant.BOT_TULING_BOT_REPLY)
        return result
