#!/usr/bin/env python
# coding: utf-8

#===================================================
from wechat import WeChat
from wechat.utils import *
from wx_handler import WeChatMsgProcessor
from wx_handler import Bot
from db import SqliteDB
from db import MysqlDB
from config import ConfigManager
from config import Constant
from config import Log
#---------------------------------------------------
import threading
import traceback
import os
import logging
import time
#===================================================


cm = ConfigManager()
msg_db = SqliteDB(cm.getpath('database'))
# db = MysqlDB(cm.mysql())
wechat_msg_processor = WeChatMsgProcessor(msg_db)
wechat = WeChat(cm.get('wechat', 'host'))

wechat.bot = Bot()
wechat.msg_handler = wechat_msg_processor
wechat_msg_processor.wechat = wechat

logger = logging.getLogger('werkzeug')
log_format_str = Constant.SERVER_LOG_FORMAT
formatter = logging.Formatter(log_format_str)

# 控制urllib3库的访问进程输出，若需要查看具体访问端口细节可以注释下列代码
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

while True:
    try:
        wechat.start()
    except KeyboardInterrupt:
        echo(Constant.LOG_MSG_QUIT)
        wechat.exit_code = 1
    else:
        Log.error(traceback.format_exc())
    finally:
        wechat.stop()

    if wechat.exit_code == 0:
        echo('断开连接，程序关闭\n')
        # 若掉线后引起的正常退出，在wechat.stop 中数据库已经关闭，
        # 机器人节点也已经关闭，再次执行wechat.start会出现一些错误
        # 所以需要推出程序，重新启动，而且就算不退出程序也需要重新扫码，并无意义
        exit()
    else:
        # kill process
        os.system(Constant.LOG_MSG_KILL_PROCESS % os.getpid())
