#!/usr/bin/env python
# coding: utf-8

#===================================================
from utils import *
from wechat_apis import WXAPI
from config import ConfigManager
from config import Constant
from config import Log
#---------------------------------------------------
import json
import re
import sys
import os
import time
import random
from collections import defaultdict
from datetime import timedelta
import traceback
import Queue
import threading
#===================================================


class WeChat(WXAPI):

    def __str__(self):
        description = \
            "=========================\n" + \
            "[#] Web WeChat\n" + \
            "[#] UUID: " + self.uuid + "\n" + \
            "[#] Uin: " + str(self.uin) + "\n" + \
            "[#] Sid: " + self.sid + "\n" + \
            "[#] Skey: " + self.skey + "\n" + \
            "[#] DeviceId: " + self.device_id + "\n" + \
            "[#] PassTicket: " + self.pass_ticket + "\n" + \
            "[#] Run Time: " + self.get_run_time() + '\n' + \
            "========================="
        return description

    def __init__(self, host='wx.qq.com'):
        super(WeChat, self).__init__(host)

        # self.save_data_folder = ''  # 保存图片，语音，小视频的文件夹   # 用途？
        # self.last_login = 0  # 上次退出的时间
        self.time_out = 2  # 同步时间间隔（单位：秒）
        # 此设置并不是越短越好
        self.start_time = time.time()
        self.msg_handler = None
        self.bot = None

        cm = ConfigManager()
        self.save_data_folders = cm.get_wechat_media_dir()  # 上面存在同名无用变量
        self.log_mode = cm.get('setting', 'log_mode') == 'True'
        self.exit_code = 0

    def start(self):
        # echo(Constant.LOG_MSG_START)
        # run(Constant.LOG_MSG_RECOVER, self.recover)

        # timeOut = time.time() - self.last_login
        # echo(Constant.LOG_MSG_TRY_INIT)
        # if self.webwxinit():
        #     echo(Constant.LOG_MSG_SUCCESS)
        #     run(Constant.LOG_MSG_RECOVER_CONTACT, self.recover_contacts)
        # else:
            # 若本地信息无法初始化微信，则需要进行重新登录
            # 上面属于未登出状态重新启动的处理
            # 正常来说都应该进行二维码验证
            # 上面处理在不需要进行帐号信息本地存储的状态下可以注释

            # echo(Constant.LOG_MSG_FAIL)

        while True:
            # first try to login by uin without qrcode
            # echo(Constant.LOG_MSG_ASSOCIATION_LOGIN)
            # if self.association_login():
                # echo(Constant.LOG_MSG_SUCCESS)
            # else:
            # echo(Constant.LOG_MSG_FAIL)
            # scan qrcode to login

            # 正常扫描二维码登录步骤

            run(Constant.LOG_MSG_GET_UUID, self.getuuid)
            echo(Constant.LOG_MSG_GET_QRCODE)
            self.genqrcode()
            echo(Constant.LOG_MSG_SCAN_QRCODE)

            if not self.waitforlogin():
                continue
            echo(Constant.LOG_MSG_CONFIRM_LOGIN)
            if not self.waitforlogin(0):
                continue
            break

        run(Constant.LOG_MSG_LOGIN, self.login)
        run(Constant.LOG_MSG_INIT, self.webwxinit)
        run(Constant.LOG_MSG_STATUS_NOTIFY, self.webwxstatusnotify)
        run(Constant.LOG_MSG_GET_CONTACT, self.webwxgetcontact)
        echo(Constant.LOG_MSG_CONTACT_COUNT % (
                self.MemberCount, len(self.MemberList)
            ))
        echo(Constant.LOG_MSG_OTHER_CONTACT_COUNT % (
                len(self.addGroupIDList), len(self.ContactList),
                len(self.SpecialUsersList), len(self.PublicUsersList)
            ))
        run(Constant.LOG_MSG_GET_GROUP_MEMBER, self.fetch_group_contacts)

        # 使用对话设置cookies
        self.cookie = self.session.cookies

        while True:
            [retcode, selector] = self.synccheck()
            Log.debug('retcode: %s, selector: %s' % (retcode, selector))
            self.exit_code = int(retcode)

            if retcode == '1100':
                echo(Constant.LOG_MSG_LOGOUT)
                break
            if retcode == '1101':
                echo(Constant.LOG_MSG_LOGIN_OTHERWHERE)
                break
            if retcode == '1102':
                echo(Constant.LOG_MSG_QUIT_ON_PHONE)
                break
            elif retcode == '0':
                if selector == '2' or selector == '4':
                    # 有新消息
                    r = self.webwxsync()
                    # 获取新消息的内容
                    # 保存群聊到通讯录
                    # 修改群名称
                    # 新增或删除联系人
                    # 群聊成员数目变化
                    if r is not None:
                        try:
                            echo('into handle_mod\n')
                            self.handle_mod(r)
                        except:
                            Log.error(traceback.format_exc())
                elif selector == '7':
                    # 进出聊天界面
                    r = self.webwxsync()
                elif selector == '0':
                    # 无更新
                    echo('no new info\n')
                    time.sleep(self.time_out)
                elif selector == '3' or selector == '6':
                    break
            else:
                r = self.webwxsync()
                Log.debug('webwxsync: %s\n' % json.dumps(r))

            # 执行定时任务
            if self.msg_handler:
                self.msg_handler.check_schedule_task()

            # 可以添加定时推送机器人
            # 也可以修改机器人后在wechat_msg_processor中添加

            if self.bot:
                pass

    def get_run_time(self):
        """
        @brief      get how long this run
        @return     String
        """
        totalTime = int(time.time() - self.start_time)
        t = timedelta(seconds=totalTime)
        return '%s Day %s' % (t.days, t)

    def stop(self):
        """
        @brief      Save some data and use shell to kill this process
        """
        # run(Constant.LOG_MSG_SNAPSHOT, self.snapshot)

        echo(Constant.LOG_MSG_RUNTIME % self.get_run_time())
        # close database connect
        if self.msg_handler:
            self.msg_handler.msg_db.close()

        # close session
        self.session.close()
        if self.bot:
            self.bot.close_session()

    def fetch_group_contacts(self):
        """
        @brief      Fetches all groups contacts.
        @return     Bool: whether operation succeed.
        @note       This function must be finished in 180s
        """
        Log.debug('fetch_group_contacts')

        max_thread_num = 4
        max_fetch_group_num = 50
        group_list_queue = Queue.Queue()

        class GroupListThread(threading.Thread):

            def __init__(self, group_list_queue, wechat):
                threading.Thread.__init__(self)
                self.group_list_queue = group_list_queue
                self.wechat = wechat

            def run(self):
                while not self.group_list_queue.empty():
                    gid_list = self.group_list_queue.get()
                    group_member_list = self.wechat.webwxbatchgetcontact(gid_list)
                    for member_list in group_member_list[:]:
                        g_member_list = member_list['MemberList'][:]
                        member_list['MemberList'] = []
                        self.wechat.GroupList.append(member_list)
                        self.wechat.GroupMemeberList[member_list['UserName']] = g_member_list

                    self.group_list_queue.task_done()

        for g_list in split_array(self.addGroupIDList, max_fetch_group_num):
            group_list_queue.put(g_list)

        for i in range(max_thread_num):
            t = GroupListThread(group_list_queue, self)
            t.setDaemon(True)
            t.start()

        group_list_queue.join()

        # 对于群成员的处理不使用数据库，直接在通过内存中的字典进行操作，
        # 因为python对于字典的优化已经做的非常不错，通过数据库进行处理并不能显著提升性能，并没有必要
        # 而且就时效性考虑，因为每次群ID都在变化，就算存入数据库中，在下次运行程序时依然要重新写入数据库
        # 所以并不能节省开销

        return True

    def handle_mod(self, r):
        # 说明：手机上对于通讯录所做的一些操作并不会百分之百反映到网页端
        # 当前网页端API的返回数据还存在大量无用的变量，即仅有变量名存在，而值一直为空值
        # 可能是微信网页端为了扩展功能而留下的

        # ModContactCount: 变更联系人或群聊成员数目
        # ModContactList: 变更联系人或群聊列表，或群名称改变
        Log.debug('handle modify')
        for m in r['ModContactList']:
            if m['UserName'][:2] == '@@':
                # group
                in_list = False
                g_id = m['UserName']
                for i in xrange(len(self.GroupList)):
                    # group member change
                    if g_id == self.GroupList[i]['UserName']:
                        in_list = True
                        group = self.webwxbatchgetcontact([g_id])[0]
                        if group:
                            self.GroupList[i] = group
                            self.GroupMemeberList[g_id] = group['MemberList'][:]
                            self.GroupList[i]['MemberList'] = []
                        break
                if not in_list:
                    # a new group
                    group = self.webwxbatchgetcontact([g_id])[0]
                    if group:
                        self.addGroupIDList.append(g_id)
                        self.GroupMemeberList[g_id] = group['MemberList'][:]
                        group['MemberList'] = []
                        self.GroupList.append(group)

            elif m['UserName'][0] == '@':
                # user
                in_list = False
                u_id = m['UserName']
                for i in xrange(len(self.MemberList)):
                    if u_id == self.MemberList[i]['UserName']:
                        self.MemberList[i] = m
                        in_list = True

                        if m['VerifyFlag'] & 8 != 0:  # 公众号/服务号
                            for j in xrange(len(self.PublicUsersList)):
                                if u_id == self.PublicUsersList[j]:
                                    self.PublicUsersList[j] = m
                                    break
                        elif u_id in self.wx_conf['SpecialUsers']:  # 特殊帐号
                            for j in xrange(len(self.SpecialUsersList)):
                                if u_id == self.SpecialUsersList[j]:
                                    self.SpecialUsersList[j] = m
                                    break
                        elif u_id != self.User['UserName']:
                            self.ContactList.append(m)
                            for j in xrange(len(self.ContactList)):
                                if u_id == self.ContactList[j]:
                                    self.ContactList[j] = m
                                    break
                        break
                # if don't have then add it
                if not in_list:
                    self.MemberList.append(m)
                    if m['VerifyFlag'] & 8 != 0:  # 公众号/服务号
                        self.PublicUsersList.append(m)
                    elif m['UserName'] in self.wx_conf['SpecialUsers']:  # 特殊帐号
                        self.SpecialUsersList.append(m)
                    elif m['UserName'] != self.User['UserName']:
                        self.ContactList.append(m)
        self.handle_msg(r)

    def handle_msg(self, r):
        """
        @brief      Handle message
                    对消息分类获取raw_msg，后处理消息
        @param      r  Dict: message json
        """
        Log.debug('handle message')

        n = len(r['AddMsgList'])
        if n == 0:
            # 权宜之计
            time.sleep(self.time_out)
            return

        if self.log_mode:
            echo(Constant.LOG_MSG_NEW_MSG % n)

        for msg in r['AddMsgList']:

            msgType = msg['MsgType']
            msgId = msg['MsgId']
            content = msg['Content'].replace('&lt;', '<').replace('&gt;', '>')
            raw_msg = None

            if msgType == self.wx_conf['MSGTYPE_TEXT']:
                # 地理位置消息
                if content.find('pictype=location') != -1:
                    if msg['FromUserName'][0:2] == '@@':
                        location = content.split(':<br/>')[1]
                    else:
                        location = content.split(':<br/>')[0]
                    raw_msg = {
                        'raw_msg': msg,
                        'location': location,
                        'text': location,
                        'log': Constant.LOG_MSG_LOCATION % location
                    }
                # 普通文本消息
                else:
                    tmp = content.split(':<br/>')
                    text = ':<br/>'.join(tmp[min(len(tmp) - 1, 1):])
                    raw_msg = {
                        'raw_msg': msg,
                        'text': text,
                        'log': text.replace('<br/>', '\n')
                    }
            elif msgType == self.wx_conf['MSGTYPE_IMAGE']:
                data = self.webwxgetmsgimg(msgId)
                fn = 'img_' + msgId + '.jpg'
                dir = self.save_data_folders['webwxgetmsgimg']
                path = save_file(fn, data, dir)
                raw_msg = {'raw_msg': msg,
                           'image': path,
                           'log': Constant.LOG_MSG_PICTURE % path}
            elif msgType == self.wx_conf['MSGTYPE_VOICE']:
                data = self.webwxgetvoice(msgId)
                fn = 'voice_' + msgId + '.mp3'
                dir = self.save_data_folders['webwxgetvoice']
                path = save_file(fn, data, dir)
                raw_msg = {'raw_msg': msg,
                           'voice': path,
                           'log': Constant.LOG_MSG_VOICE % path}
            elif msgType == self.wx_conf['MSGTYPE_SHARECARD']:
                info = msg['RecommendInfo']
                card = Constant.LOG_MSG_NAME_CARD % (
                    info['NickName'],
                    info['Alias'],
                    info['Province'], info['City'],
                    Constant.LOG_MSG_SEX_OPTION[info['Sex']]
                )
                namecard = '%s %s %s %s %s' % (
                    info['NickName'], info['Alias'], info['Province'],
                    info['City'], Constant.LOG_MSG_SEX_OPTION[info['Sex']]
                )
                raw_msg = {
                    'raw_msg': msg,
                    'namecard': namecard,
                    'log': card
                }
            elif msgType == self.wx_conf['MSGTYPE_EMOTICON']:
                url = search_content('cdnurl', content)
                raw_msg = {'raw_msg': msg,
                           'emoticon': url,
                           'log': Constant.LOG_MSG_EMOTION % url}
            elif msgType == self.wx_conf['MSGTYPE_APP']:
                card = ''
                # 链接, 音乐, 微博
                if msg['AppMsgType'] in [
                    self.wx_conf['APPMSGTYPE_AUDIO'],
                    self.wx_conf['APPMSGTYPE_URL'],
                    self.wx_conf['APPMSGTYPE_OPEN']
                ]:
                    card = Constant.LOG_MSG_APP_LINK % (
                        Constant.LOG_MSG_APP_LINK_TYPE[msg['AppMsgType']],
                        msg['FileName'],
                        search_content('des', content, 'xml'),
                        msg['Url'],
                        search_content('appname', content, 'xml')
                    )
                    raw_msg = {
                        'raw_msg': msg,
                        'link': msg['Url'],
                        'log': card
                    }
                # 图片
                elif msg['AppMsgType'] == self.wx_conf['APPMSGTYPE_IMG']:
                    data = self.webwxgetmsgimg(msgId)
                    fn = 'img_' + msgId + '.jpg'
                    dir = self.save_data_folders['webwxgetmsgimg']
                    path = save_file(fn, data, dir)
                    card = Constant.LOG_MSG_APP_IMG % (
                        path,
                        search_content('appname', content, 'xml')
                    )
                    raw_msg = {
                        'raw_msg': msg,
                        'image': path,
                        'log': card
                    }
                else:
                    raw_msg = {
                        'raw_msg': msg,
                        'log': Constant.LOG_MSG_UNKNOWN_MSG % (msgType, content)
                    }
            elif msgType == self.wx_conf['MSGTYPE_STATUSNOTIFY']:
                Log.info(Constant.LOG_MSG_NOTIFY_PHONE)
            elif msgType == self.wx_conf['MSGTYPE_MICROVIDEO']:
                data = self.webwxgetvideo(msgId)
                fn = 'video_' + msgId + '.mp4'
                dir = self.save_data_folders['webwxgetvideo']
                path = save_file(fn, data, dir)
                raw_msg = {'raw_msg': msg,
                           'video': path,
                           'log': Constant.LOG_MSG_VIDEO % path}
            elif msgType == self.wx_conf['MSGTYPE_RECALLED']:
                recall_id = search_content('msgid', content, 'xml')
                text = Constant.LOG_MSG_RECALL
                raw_msg = {
                    'raw_msg': msg,
                    'text': text,
                    'recall_msg_id': recall_id,
                    'log': text
                }
            elif msgType == self.wx_conf['MSGTYPE_SYS']:
                raw_msg = {
                    'raw_msg': msg,
                    'sys_notif': content,
                    'log': content
                }
            elif msgType == self.wx_conf['MSGTYPE_VERIFYMSG']:
                name = search_content('fromnickname', content)
                raw_msg = {
                    'raw_msg': msg,
                    'log': Constant.LOG_MSG_ADD_FRIEND % name
                }
            elif msgType == self.wx_conf['MSGTYPE_VIDEO']:
                # 暂时无法对该类型进行处理，即视频信息
                raw_msg = {
                    'raw_msg': msg,
                    'log': Constant.LOG_MSG_UNKNOWN_MSG % (msgType, content)
                }
            else:
                raw_msg = {
                    'raw_msg': msg,
                    'log': Constant.LOG_MSG_UNKNOWN_MSG % (msgType, content)
                }

            # 此处对消息进行处理，具体请修改handle_user_msg与handle_group_msg

            isGroupMsg = '@@' in msg['FromUserName']+msg['ToUserName']
            if self.msg_handler and raw_msg:
                if isGroupMsg:
                    # handle group messages
                    g_msg = self.make_group_msg(raw_msg)
                    self.msg_handler.handle_group_msg(g_msg)  #
                else:
                    # handle personal messages
                    self.msg_handler.handle_user_msg(raw_msg)  #

            if self.log_mode:
                self.show_msg(raw_msg)

    def make_group_msg(self, msg):
        """
        @brief      Package the group message for storage.
        @param      msg  Dict: raw msg
        @return     raw_msg Dict: packged msg
        """
        Log.debug('make group message')
        raw_msg = {
            'raw_msg': msg['raw_msg'],
            'msg_id': msg['raw_msg']['MsgId'],
            'group_owner_uin': '',
            'group_name': '',
            'group_count': '',
            'from_user_name': msg['raw_msg']['FromUserName'],
            'to_user_name': msg['raw_msg']['ToUserName'],
            'user_attrstatus': '',
            'user_display_name': '',
            'user_nickname': '',
            'msg_type': msg['raw_msg']['MsgType'],
            'text': '',
            'link': '',
            'image': '',
            'video': '',
            'voice': '',
            'emoticon': '',
            'namecard': '',
            'location': '',
            'recall_msg_id': '',
            'sys_notif': '',
            'time': '',
            'timestamp': '',
            'log': '',
        }
        content = msg['raw_msg']['Content'].replace(
            '&lt;', '<').replace('&gt;', '>')

        group = None
        src = None

        if msg['raw_msg']['FromUserName'][:2] == '@@':
            # 接收到来自群的消息
            g_id = msg['raw_msg']['FromUserName']
            group = self.get_group_by_id(g_id)

            if re.search(":<br/>", content, re.IGNORECASE):
                u_id = content.split(':<br/>')[0]
                src = self.get_group_user_by_id(u_id, g_id)

        elif msg['raw_msg']['ToUserName'][:2] == '@@':
            # 自己发给群的消息
            g_id = msg['raw_msg']['ToUserName']
            u_id = msg['raw_msg']['FromUserName']
            src = self.get_group_user_by_id(u_id, g_id)
            group = self.get_group_by_id(g_id)

        if src:
            raw_msg['user_attrstatus'] = src['AttrStatus']
            raw_msg['user_display_name'] = src['DisplayName']
            raw_msg['user_nickname'] = src['NickName']
        if group:
            raw_msg['group_count'] = group['MemberCount']
            raw_msg['group_owner_uin'] = group['OwnerUin']
            raw_msg['group_name'] = group['ShowName']

        raw_msg['timestamp'] = msg['raw_msg']['CreateTime']
        t = time.localtime(float(raw_msg['timestamp']))
        raw_msg['time'] = time.strftime("%Y-%m-%d %T", t)

        for key in [
            'text', 'link', 'image', 'video', 'voice',
            'emoticon', 'namecard', 'location', 'log',
            'recall_msg_id', 'sys_notif'
        ]:
            if key in msg:
                raw_msg[key] = msg[key]

        return raw_msg

    def show_msg(self, message):
        """
        @brief      Log the message to stdout
        @param      message  Dict
        """
        msg = message
        src = None
        dst = None
        group = None

        if msg and msg['raw_msg']:

            content = msg['raw_msg']['Content']
            content = content.replace('&lt;', '<').replace('&gt;', '>')
            msg_id = msg['raw_msg']['MsgId']

            if msg['raw_msg']['FromUserName'][:2] == '@@':
                # 接收到来自群的消息
                g_id = msg['raw_msg']['FromUserName']
                group = self.get_group_by_id(g_id)

                if re.search(":<br/>", content, re.IGNORECASE):
                    u_id = content.split(':<br/>')[0]
                    src = self.get_group_user_by_id(u_id, g_id)
                    dst = {'ShowName': 'GROUP'}
                else:
                    u_id = msg['raw_msg']['ToUserName']
                    src = {'ShowName': 'SYSTEM'}
                    dst = self.get_group_user_by_id(u_id, g_id)
            elif msg['raw_msg']['ToUserName'][:2] == '@@':
                # 自己发给群的消息
                g_id = msg['raw_msg']['ToUserName']
                u_id = msg['raw_msg']['FromUserName']
                group = self.get_group_by_id(g_id)
                src = self.get_group_user_by_id(u_id, g_id)
                dst = {'ShowName': 'GROUP'}
            else:
                # 非群聊消息
                src = self.get_user_by_id(msg['raw_msg']['FromUserName'])
                dst = self.get_user_by_id(msg['raw_msg']['ToUserName'])

            if group:
                echo('%s |%s| %s -> %s: %s\n' % (
                    msg_id,
                    trans_emoji(group['ShowName']),
                    trans_emoji(src['ShowName']),
                    dst['ShowName'],
                    trans_emoji(msg['log'])
                ))
            else:
                echo('%s %s -> %s: %s\n' % (
                    msg_id,
                    trans_emoji(src['ShowName']),
                    trans_emoji(dst['ShowName']),
                    trans_emoji(msg['log'])
                ))
