#!/usr/bin/env python
# coding: utf-8

#===================================================
from wechat.utils import *
from config import Constant
#---------------------------------------------------
import random, time, json
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

    def tuling_reply(self, text):
        ''' 可以修改自动回复的查询链接，此为Bot的自动回复功能函数
            @param  text：消息内容
            @return: 自动回复信息
        ''' 
        APIKEY = Constant.BOT_TULING_API_KEY
        api_url = Constant.BOT_TULING_API_URL % (APIKEY, text, '12345678')
        r = json.loads(get(self.tuling_session, api_url))
        if r.get('code') == 100000 and r.get('text') != Constant.BOT_TULING_BOT_REPLY:
            return r['text']
        return ''
