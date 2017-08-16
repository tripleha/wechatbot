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

        self.time_out = 2  # 同步时间间隔（单位：秒）此设置并不是越短越好
        self.start_time = time.time()
        self.msg_handler = None
        self.bot = None

        cm = ConfigManager()
        self.save_data_folders = cm.get_wechat_media_dir()
        self.log_mode = cm.get('setting', 'log_mode') == 'True'
        self.exit_code = 0

        # 用于处理信息的类内全局
        self.CommandList = []
        self.DBStoreMSGList = []
        self.GroupNeedReplyList = []
        self.UserNeedReplyList = []
        self.ReplyList = []
        self.DBStoreBOTReplyList = []

        self.AddUserList = []  # 等待添加为好友的用户

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
                if selector == '2' or selector == '4' or selector == '7' or selector == '6' or selector == '3':
                    # 6 -> 新朋友，3 -> 自己信息的修改，
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
                elif selector == '0':
                    # 无更新
                    echo('no new info\n')
                    time.sleep(self.time_out)
            else:
                r = self.webwxsync()
                Log.debug('webwxsync: %s\n' % json.dumps(r))

            # 执行定时任务
            if self.msg_handler:
                flag = self.msg_handler.check_exit()
                if flag:
                    echo('达到运行时长，即将退出\n')
                    break

    def get_run_time(self):
        total_time = int(time.time() - self.start_time)
        t = timedelta(seconds=total_time)
        return '%s Day %s' % (t.days, t)

    def add_operate_list(self, msg, flag):
        text = msg['text']
        if flag:
            if msg['FromUser']['UserName'][0:2] == '@@':
                # 群 -> 我
                if msg['FromUser']['NickName']:
                    table = 'groupz' + trans_unicode_into_int(trans_coding(msg['FromUser']['NickName']))
                else:
                    # 无名称的群
                    table = 'groupz' + trans_unicode_into_int(trans_coding('Group'))
                self.msg_handler.msg_db.create_table(table, self.msg_handler.msg_col)
                reply_flag = False
                r = re.findall(u'@[^@\u2005]+\u2005', trans_coding(text))
                if r:
                    for m in r:
                        name = m[1:-1].encode('utf-8')
                        if name == msg['ToUser']['ShowName'] or name == self.User['NickName']:
                            cmd = re.sub(m, '', trans_coding(text)).encode('utf-8')
                            add_cmd = {}
                            if cmd == 'check_record_count':
                                add_cmd['func'] = 'check_count'
                                add_cmd['time'] = msg['raw_msg']['CreateTime']
                                add_cmd['table_name'] = table
                                add_cmd['to_id'] = msg['FromUser']['UserName']
                                self.CommandList.append(add_cmd)
                            elif re.match(r'^check_record_\d+$', cmd):
                                add_cmd['func'] = 'check_text'
                                add_cmd['time'] = msg['raw_msg']['CreateTime']
                                add_cmd['msg_order'] = int(re.sub(r'^check_record_', '', cmd))
                                add_cmd['table_name'] = table
                                add_cmd['to_id'] = msg['FromUser']['UserName']
                                self.CommandList.append(add_cmd)
                            elif cmd == 'runtime':
                                add_cmd['func'] = 'check_time'
                                add_cmd['time'] = msg['raw_msg']['CreateTime']
                                add_cmd['to_id'] = msg['FromUser']['UserName']
                                self.CommandList.append(add_cmd)

                            # 好友添加命令测试
                            elif cmd == 'check_add_user':
                                add_cmd['func'] = 'check_add'
                                add_cmd['time'] = msg['raw_msg']['CreateTime']
                                add_cmd['to_id'] = msg['FromUser']['UserName']
                                self.CommandList.append(add_cmd)
                            elif re.match(r'^add_user_\d+$', cmd):
                                add_cmd['func'] = 'add_user'
                                add_cmd['time'] = msg['raw_msg']['CreateTime']
                                add_cmd['add_order'] = int(re.sub(r'^add_user_', '', cmd))
                                add_cmd['to_id'] = msg['FromUser']['UserName']
                                self.CommandList.append(add_cmd)

                            # 在上面定义命令
                            else:
                                # 下面为要自动回复内容
                                add_reply = {}
                                add_reply['text'] = cmd
                                add_reply['time'] = msg['raw_msg']['CreateTime']
                                add_reply['user'] = table
                                add_reply['to_id'] = msg['FromUser']['UserName']
                                add_reply['to_who'] = msg['FromWho']['ShowName']
                                self.GroupNeedReplyList.append(add_reply)

                                # 添加储存
                                add_store = {}
                                add_store['content'] = text
                                add_store['time'] = msg['raw_msg']['CreateTime']
                                add_store['from'] = msg['FromWho']['NickName']
                                add_store['to'] = 'Group'
                                add_store['table_name'] = table
                                self.DBStoreMSGList.append(add_store)
                            reply_flag = True
                            break
                if not reply_flag:
                    add_store = {}
                    add_store['content'] = text
                    add_store['time'] = msg['raw_msg']['CreateTime']
                    add_store['from'] = msg['FromWho']['NickName']
                    add_store['to'] = 'Group'
                    add_store['table_name'] = table
                    self.DBStoreMSGList.append(add_store)
            else:
                # 人 -> 我
                table_flag = True
                if msg['FromUser']['user_flag'] == 2:  # 特殊帐号内容不做记录
                    table_flag = False
                elif msg['FromUser']['user_flag'] == 3:
                    table = 'unknownz' + trans_unicode_into_int(trans_coding(msg['FromUser']['NickName']))
                elif msg['FromUser']['user_flag'] == 4:
                    table = 'publicz' + trans_unicode_into_int(trans_coding(msg['FromUser']['NickName']))
                elif msg['FromUser']['user_flag'] == 1:
                    table = 'normalz' + trans_unicode_into_int(trans_coding(msg['FromUser']['NickName']))
                if table_flag:
                    self.msg_handler.msg_db.create_table(table, self.msg_handler.msg_col)
                    add_cmd = {}
                    if text == 'check_record_count':
                        add_cmd['func'] = 'check_count'
                        add_cmd['time'] = msg['raw_msg']['CreateTime']
                        add_cmd['table_name'] = table
                        add_cmd['to_id'] = msg['FromUser']['UserName']
                        self.CommandList.append(add_cmd)
                    elif re.match(r'^check_record_\d+$', text):
                        add_cmd['func'] = 'check_text'
                        add_cmd['time'] = msg['raw_msg']['CreateTime']
                        add_cmd['msg_order'] = int(re.sub(r'^check_record_', '', text))
                        add_cmd['table_name'] = table
                        add_cmd['to_id'] = msg['FromUser']['UserName']
                        self.CommandList.append(add_cmd)
                    elif text == 'runtime':
                        add_cmd['func'] = 'check_time'
                        add_cmd['time'] = msg['raw_msg']['CreateTime']
                        add_cmd['to_id'] = msg['FromUser']['UserName']
                        self.CommandList.append(add_cmd)

                    # 好友添加命令测试
                    elif text == 'check_add_user':
                        add_cmd['func'] = 'check_add'
                        add_cmd['time'] = msg['raw_msg']['CreateTime']
                        add_cmd['to_id'] = msg['FromUser']['UserName']
                        self.CommandList.append(add_cmd)
                    elif re.match(r'^add_user_\d+$', text):
                        add_cmd['func'] = 'add_user'
                        add_cmd['time'] = msg['raw_msg']['CreateTime']
                        add_cmd['add_order'] = int(re.sub(r'^add_user_', '', text))
                        add_cmd['to_id'] = msg['FromUser']['UserName']
                        self.CommandList.append(add_cmd)

                    # 在上面定义命令
                    else:
                        # 下面为要自动回复内容
                        add_reply = {}
                        add_reply['text'] = text
                        add_reply['time'] = msg['raw_msg']['CreateTime']
                        add_reply['user'] = table
                        add_reply['to_id'] = msg['FromUser']['UserName']
                        self.UserNeedReplyList.append(add_reply)

                        # 添加储存
                        add_store = {}
                        add_store['content'] = text
                        add_store['time'] = msg['raw_msg']['CreateTime']
                        add_store['from'] = msg['FromUser']['NickName']
                        add_store['to'] = 'myself'
                        add_store['table_name'] = table
                        self.DBStoreMSGList.append(add_store)
        else:
            # 我 -> 群/人
            table_flag = True
            if msg['ToUser']['UserName'][0:2] == '@@':  # 群
                if msg['ToUser']['NickName']:
                    table = 'groupz' + trans_unicode_into_int(trans_coding(msg['FromUser']['NickName']))
                else:
                    # 无名称的群
                    table = 'groupz' + trans_unicode_into_int(trans_coding('Group'))
            else:
                if msg['ToUser']['user_flag'] == 2:  # 特殊帐号内容不做记录
                    table_flag = False
                elif msg['ToUser']['user_flag'] == 3:  # 未知用户内容，若与公众号聊天但未加其好友可能会出现
                    table = 'unknownz' + trans_unicode_into_int(trans_coding(msg['ToUser']['NickName']))
                elif msg['ToUser']['user_flag'] == 4:  # 公众号内容，服务号也归入其中
                    table = 'publicz' + trans_unicode_into_int(trans_coding(msg['ToUser']['NickName']))
                elif msg['ToUser']['user_flag'] == 1:  # 普通用户
                    table = 'normalz' + trans_unicode_into_int(trans_coding(msg['ToUser']['NickName']))
            if table_flag:
                self.msg_handler.msg_db.create_table(table, self.msg_handler.msg_col)
                add_store = {}
                add_store['content'] = text
                add_store['time'] = msg['raw_msg']['CreateTime']
                add_store['from'] = 'myself'
                if table[0] == 'g':
                    add_store['to'] = 'Group'
                else:
                    add_store['to'] = msg['ToUser']['NickName']
                add_store['table_name'] = table
                self.DBStoreMSGList.append(add_store)

    def stop(self):
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

        # 更新自己的信息
        if r['Profile']['UserName']['Buff'] == self.User['UserName']:
            self.User['NickName'] = r['Profile']['NickName']['Buff']

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
                                if u_id == self.PublicUsersList[j]['UserName']:
                                    self.PublicUsersList[j] = m
                                    break
                        elif u_id in self.wx_conf['SpecialUsers']:  # 特殊帐号
                            for j in xrange(len(self.SpecialUsersList)):
                                if u_id == self.SpecialUsersList[j]['UserName']:
                                    self.SpecialUsersList[j] = m
                                    break
                        elif u_id != self.User['UserName']:
                            for j in xrange(len(self.ContactList)):
                                if u_id == self.ContactList[j]['UserName']:
                                    self.ContactList[j] = m
                                    break
                        break
                # a new contact
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
        Log.debug('handle message')

        n = len(r['AddMsgList'])
        if n == 0:
            # 权宜之计
            time.sleep(self.time_out)
            return

        if self.log_mode:
            echo(Constant.LOG_MSG_NEW_MSG % n)

        for raw_msg in r['AddMsgList']:

            msgType = raw_msg['MsgType']
            msgId = raw_msg['MsgId']
            content = raw_msg['Content'].replace('&lt;', '<').replace('&gt;', '>')
            content = trans_coding(content).encode('utf-8')

            rmsg = {}
            reply_flag = False

            # 获取收发人信息
            from_id = raw_msg['FromUserName']
            to_id = raw_msg['ToUserName']
            if from_id[0:2] == '@@':
                from_user = self.get_group_by_id(from_id)
                if re.search(":<br/>", content, re.IGNORECASE):
                    who_id = content.split(':<br/>')[0]
                    from_who = self.get_group_user_by_id(who_id, from_id)
                    rmsg['FromWho'] = from_who
                to_user = self.get_group_user_by_id(to_id, from_id)
                content_use = ':<br/>'.join(content.split(':<br/>')[1:])
                reply_flag = True
            elif to_id[0:2] == '@@':
                from_user = self.get_group_user_by_id(from_id, to_id)
                to_user = self.get_group_by_id(to_id)
                echo(content + '\n')
                content_use = ':<br/>'.join(content.split(':<br/>')[1:])
            else:
                from_user = self.get_user_by_id(from_id)
                to_user = self.get_user_by_id(to_id)
                content_use = content
                if from_id != self.User['UserName']:
                    reply_flag = True

            rmsg['raw_msg'] = raw_msg
            rmsg['FromUser'] = from_user
            rmsg['ToUser'] = to_user

            # 消息内容分类获取
            if msgType == self.wx_conf['MSGTYPE_TEXT']:
                # 地理位置消息
                if content_use.find('pictype=location') != -1:
                    location = content_use.split(':<br/>')[0]
                    rmsg['location'] = location
                    rmsg['text'] = location
                    rmsg['log'] = Constant.LOG_MSG_LOCATION % location
                # 普通文本消息
                else:
                    rmsg['text'] = content_use
                    rmsg['log'] = content_use

                # 文字信息分类处理
                self.add_operate_list(rmsg, reply_flag)

            elif msgType == self.wx_conf['MSGTYPE_IMAGE']:
                data = self.webwxgetmsgimg(msgId)
                fn = 'img_' + msgId + '.jpg'
                dir = self.save_data_folders['webwxgetmsgimg']
                path = save_file(fn, data, dir)
                rmsg['text'] = '[图片]'
                rmsg['image'] = path
                rmsg['log'] = Constant.LOG_MSG_PICTURE % path
            elif msgType == self.wx_conf['MSGTYPE_VOICE']:
                data = self.webwxgetvoice(msgId)
                fn = 'voice_' + msgId + '.mp3'
                dir = self.save_data_folders['webwxgetvoice']
                path = save_file(fn, data, dir)
                rmsg['text'] = '[音频]'
                rmsg['voice'] = path
                rmsg['log'] = Constant.LOG_MSG_VOICE % path
            elif msgType == self.wx_conf['MSGTYPE_SHARECARD']:
                info = raw_msg['RecommendInfo']
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
                rmsg['text'] = '[名片]' + trans_coding(namecard).encode('utf-8')
                rmsg['namecard'] = namecard
                rmsg['log'] = card
            elif msgType == self.wx_conf['MSGTYPE_EMOTICON']:
                url = search_content('cdnurl', content_use)
                rmsg['text'] = '[表情]'
                rmsg['emoticon'] = url
                rmsg['log'] = Constant.LOG_MSG_EMOTION % url
            elif msgType == self.wx_conf['MSGTYPE_APP']:
                card = ''
                # 链接, 音乐, 微博
                if raw_msg['AppMsgType'] in [
                    self.wx_conf['APPMSGTYPE_AUDIO'],
                    self.wx_conf['APPMSGTYPE_URL'],
                    self.wx_conf['APPMSGTYPE_OPEN']
                ]:
                    card = Constant.LOG_MSG_APP_LINK % (
                        Constant.LOG_MSG_APP_LINK_TYPE[raw_msg['AppMsgType']],
                        raw_msg['FileName'],
                        search_content('des', content_use, 'xml'),
                        raw_msg['Url'],
                        search_content('appname', content_use, 'xml')
                    )
                    rmsg['text'] = '[分享链接]'
                    rmsg['link'] = raw_msg['Url']
                    rmsg['log'] = card
                # 图片
                elif raw_msg['AppMsgType'] == self.wx_conf['APPMSGTYPE_IMG']:
                    data = self.webwxgetmsgimg(msgId)
                    fn = 'img_' + msgId + '.jpg'
                    dir = self.save_data_folders['webwxgetmsgimg']
                    path = save_file(fn, data, dir)
                    card = Constant.LOG_MSG_APP_IMG % (
                        path,
                        search_content('appname', content_use, 'xml')
                    )
                    rmsg['text'] = '[图片]'
                    rmsg['image'] = path
                    rmsg['log'] = card
                else:
                    rmsg['text'] = ''
                    rmsg['log'] = Constant.LOG_MSG_UNKNOWN_MSG % (msgType, content_use)
            elif msgType == self.wx_conf['MSGTYPE_STATUSNOTIFY']:
                Log.info(Constant.LOG_MSG_NOTIFY_PHONE)
                rmsg['text'] = '[状态通知]'
                rmsg['log'] = Constant.LOG_MSG_NOTIFY_PHONE[:-1]
            elif msgType == self.wx_conf['MSGTYPE_MICROVIDEO']:
                data = self.webwxgetvideo(msgId)
                fn = 'video_' + msgId + '.mp4'
                dir = self.save_data_folders['webwxgetvideo']
                path = save_file(fn, data, dir)
                rmsg['text'] = '[小视频]'
                rmsg['video'] = path
                rmsg['log'] = Constant.LOG_MSG_VIDEO % path
            elif msgType == self.wx_conf['MSGTYPE_RECALLED']:
                recall_id = search_content('msgid', content_use, 'xml')
                text = Constant.LOG_MSG_RECALL
                rmsg['text'] = text
                rmsg['recall_msg_id'] = recall_id
                rmsg['log'] = text
            elif msgType == self.wx_conf['MSGTYPE_SYS']:
                rmsg['text'] = content_use
                rmsg['sys_notif'] = content_use
                rmsg['log'] = content_use
            elif msgType == self.wx_conf['MSGTYPE_VERIFYMSG']:
                name = search_content('fromnickname', content_use)
                rmsg['text'] = '[添加好友请求]'
                rmsg['log'] = Constant.LOG_MSG_ADD_FRIEND % name

                # 好友自动同意在此处添加
                count = len(self.AddUserList)
                add_user = {
                    'Order': count + 1,
                    'UserName': raw_msg['RecommendInfo']['UserName'],
                    'NickName': raw_msg['RecommendInfo']['NickName'],
                    'Ticket': raw_msg['RecommendInfo']['Ticket']
                }
                self.AddUserList.append(add_user)
                # 先添加与列表中，之后可根据命令提示来允许添加谁

            elif msgType == self.wx_conf['MSGTYPE_VIDEO']:
                # 暂时无法对该类型进行处理，即视频信息
                rmsg['text'] = '[视频消息]'
                rmsg['log'] = Constant.LOG_MSG_UNKNOWN_MSG % (msgType, content_use)
            else:
                rmsg['text'] = ''
                rmsg['log'] = Constant.LOG_MSG_UNKNOWN_MSG % (msgType, content_use)

            if self.log_mode:
                self.show_msg(rmsg)

        try:
            if self.msg_handler:
                self.msg_handler.save_into_db(self.DBStoreMSGList)
                self.msg_handler.handle_commands(self.CommandList)
                self.msg_handler.get_bot_reply(self.GroupNeedReplyList, self.UserNeedReplyList)
                self.msg_handler.auto_reply(self.ReplyList)
                self.msg_handler.save_into_db(self.DBStoreBOTReplyList)
        except:
            traceback.print_exc()
            Log.error(traceback.format_exc())
        finally:
            self.CommandList = []
            self.DBStoreMSGList = []
            self.GroupNeedReplyList = []
            self.UserNeedReplyList = []
            self.ReplyList = []
            self.DBStoreBOTReplyList = []

    def show_msg(self, message):
        """
        @brief      Log the message to stdout
        @param      message  Dict
        """
        msg = message
        src = msg['FromUser']
        dst = msg['ToUser']
        group = None
        msg_id = msg['raw_msg']['MsgId']

        if msg['FromUser']['UserName'][0:2] == '@@':
            group = msg['FromUser']
            if 'FromWho' in msg:
                src = msg['FromWho']
            else:
                src = {'ShowName': 'SYSTEM'}
        elif msg['ToUser']['UserName'][0:2] == '@@':
            group = msg['ToUser']
            dst = {'ShowName': 'GROUP'}

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

'''
    msg应该包含的三个值：
    raw_msg：原封不动的刷新返回数据
    FromUser：发出用户的信息
    ToUser：发向用户的信息
    
    扩展内容：
    对于组：还需要一个FromWho表示发送该消息的用户信息
    text：提取的文本内容，UTF-8格式
    log：打印到控制台的内容
'''
