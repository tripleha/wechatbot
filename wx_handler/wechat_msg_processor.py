#!/usr/bin/env python
# coding: utf-8

#===================================================
from wechat.utils import *
from config import ConfigManager
from config import Constant
from config import Log
#---------------------------------------------------
import os
import time
from datetime import timedelta
import json
import re
#===================================================


class WeChatMsgProcessor(object):
    """
    Process fetched data
    """

    def __init__(self, msg_db):

        self.wechat = None  # recieve `WeChat` class instance
                            # for call some wechat apis

        self.msg_db = msg_db

        self.msg_col = '''
            MsgOrder integer primary key,
            Time text,
            FromNick text,
            ToNick text,
            content text
        '''
        self.user_type = ['normal', 'group', 'public', 'unknown']

    def get_time_string(self, second=0):
        if second:
            return time.strftime('%Y-%m-%d,%H:%M:%S', time.localtime(second))
        return time.strftime('%Y-%m-%d,%H:%M:%S', time.localtime(time.time()))

    def save_into_db(self, store_list):
        stores = sorted(store_list, key=lambda x: x['time'])
        for s in stores:
            col = (
                None,
                self.get_time_string(s['time']),
                s['from'],
                s['to'],
                s['content']
            )
            self.msg_db.insert(s['table_name'], col)

    def handle_commands(self, command_list):
        commands = sorted(command_list, key=lambda x: x['time'])
        for cmd in commands:
            add_reply = {}
            if cmd['func'] == 'check_count':
                max_count = self.msg_db.select_max(cmd['table_name'], "MsgOrder")
                add_reply['text'] = str(max_count)
                add_reply['to_id'] = cmd['to_id']
                self.wechat.ReplyList.append(add_reply)
            elif cmd['func'] == 'check_text':
                record = self.msg_db.select(cmd['table_name'], "MsgOrder", cmd['msg_order'])
                if record:
                    record_msg = 'MsgOrder:' + str(record[0]['MsgOrder']) + ' ' + \
                                 'Time:' + record[0]['Time'] + ' ' + \
                                 'From:' + record[0]['FromNick'] + ' ' + \
                                 'To:' + record[0]['ToNick'] + ' ' + \
                                 'content:' + record[0]['content']
                else:
                    record_msg = '记录无效'
                add_reply['text'] = record_msg
                add_reply['to_id'] = cmd['to_id']
                self.wechat.ReplyList.append(add_reply)
            elif cmd['func'] == 'check_time':
                add_reply['text'] = self.wechat.get_run_time()
                add_reply['to_id'] = cmd['to_id']
                self.wechat.ReplyList.append(add_reply)

            # 添加好友命令测试
            elif cmd['func'] == 'check_add':
                text = ' '.join([str(u['Order']) + '_' + u['NickName']
                                for u in self.wechat.AddUserList])
                add_reply['text'] = text + ' '
                add_reply['to_id'] = cmd['to_id']
                self.wechat.ReplyList.append(add_reply)
            elif cmd['func'] == 'add_user':
                find_list = [u for u in self.wechat.AddUserList if u['Order'] == cmd['add_order']]
                if len(find_list):
                    flag = self.wechat.accept_friend(find_list[0]['UserName'], find_list[0]['Ticket'])
                    if flag:
                        add_reply['text'] = '添加成功'
                    else:
                        add_reply['text'] = '添加失败'
                else:
                    add_reply['text'] = '无该索引'
                add_reply['to_id'] = cmd['to_id']
                self.wechat.ReplyList.append(add_reply)

    def get_bot_reply(self, group_r_list, user_r_list):
        if len(group_r_list) == 0 and len(user_r_list) == 0:
            return

        r_groups = sorted(group_r_list, key=lambda x: x['time'])
        r_users = sorted(user_r_list, key=lambda x: x['time'])

        if len(group_r_list) != 0:
            g_rs = self.wechat.bot.get_many_reply(r_groups)
            for i in xrange(0, len(g_rs)):
                add_reply = {}
                text = u'@' + trans_coding(group_r_list[i]['to_who']) + u'\u2005' + trans_coding(g_rs[i])
                add_reply['text'] = text.encode('utf-8')
                add_reply['to_id'] = group_r_list[i]['to_id']
                add_reply['table'] = group_r_list[i]['user']
                self.wechat.ReplyList.append(add_reply)
        if len(user_r_list) != 0:
            u_rs = self.wechat.bot.get_many_reply(r_users)
            for i in xrange(0, len(u_rs)):
                add_reply = {}
                add_reply['text'] = u_rs[i].encode('utf-8')
                add_reply['to_id'] = user_r_list[i]['to_id']
                add_reply['table'] = user_r_list[i]['user']
                self.wechat.ReplyList.append(add_reply)

    def auto_reply(self, reply_list):
        for reply in reply_list:
            flag = self.wechat.send_text(reply['to_id'], reply['text'])
            if 'table' in reply:
                add_store = {}
                add_store['time'] = int(time.time())
                add_store['content'] = reply['text']
                add_store['from'] = 'myself-bot'
                if reply['to_id'][0:2] == '@@':
                    add_store['to'] = 'Group'
                else:
                    add_store['to'] = trans_int_into_unicode(reply['table'])[1].encode('utf-8')
                add_store['table_name'] = reply['table']
                self.wechat.DBStoreBOTReplyList.append(add_store)
            if flag:
                echo('自动回复成功\n')
            else:
                echo('自动回复失败\n')

    # def handle_group_msg(self, msg):
    #     """
    #     @brief      Recieve group messages
    #     @param      msg  Dict: packaged msg
    #     """
    #     # 获取群ID
    #     if msg['raw_msg']['FromUserName'][:2] == '@@':
    #         g_id = msg['raw_msg']['FromUserName']
    #     else:
    #         g_id = msg['raw_msg']['ToUserName']
    #     # add new group
    #     # 貌似此步骤可以省略
    #     if g_id not in self.wechat.addGroupIDList:
    #         group = self.wechat.webwxbatchgetcontact([g_id])[0]
    #         if group:
    #             self.wechat.addGroupIDList.append(g_id)
    #             self.wechat.GroupMemeberList['g_id'] = group['MemberList'][:]
    #             group['MemberList'] = []
    #             self.wechat.GroupList.append(group)
    #
    #             # 留做检查用，若出现则说明不应省略此处
    #             echo('add group in msg handler\n')
    #
    #     wechat = self.wechat
    #     if msg['raw_msg']['MsgType'] != wechat.wx_conf['MSGTYPE_TEXT']:
    #         # 当前只对文本消息进行处理/提取出的地理位置消息也算在内
    #         return
    #
    #     # 获取说话者ID
    #     content = msg['raw_msg']['Content'].replace('&lt;', '<').replace('&gt;', '>')
    #     from_id = content.split(':<br/>')[0]
    #     from_usr = wechat.get_group_user_by_id(from_id, g_id)
    #
    #     # 查看是否创建表
    #     t_group = wechat.get_group_by_id(g_id)
    #     if t_group['NickName']:
    #         table_name = 'groupz' + trans_unicode_into_int(trans_coding(t_group['NickName']))
    #     else:
    #         table_name = 'groupz' + trans_unicode_into_int(trans_coding('Group'))
    #     self.msg_db.create_table(table_name, self.msg_col)
    #
    #     text = msg['text']
    #     r = re.findall(u'@[^\u2005]+\u2005', trans_coding(text))
    #     op_flag = False
    #     if r and from_id != wechat.User['UserName']:
    #         usr_self = wechat.get_group_user_by_id(wechat.User['UserName'], g_id)
    #         for m in r:
    #             name = m[1:-1].encode('utf-8')
    #             if name == usr_self['ShowName'] or name == wechat.User['NickName']:
    #                 # 进入对于@自己 的消息的处理
    #                 self.handle_command(re.sub(m, '', trans_coding(text)).encode('utf-8'),
    #                                     msg, t_group, from_usr, table_name)
    #                 op_flag = True
    #                 break
    #     if not op_flag:
    #         col = (
    #             None,
    #             self.get_time_string(msg['raw_msg']['CreateTime']),
    #             from_usr['NickName'],
    #             'Group',
    #             trans_coding(text).encode('utf-8')
    #         )
    #         self.msg_db.insert(table_name, col)
    #
    # def handle_user_msg(self, msg):
    #     """
    #     @brief      Recieve personal messages
    #     @param      msg  Dict
    #     """
    #     wechat = self.wechat
    #
    #     if msg['raw_msg']['MsgType'] != wechat.wx_conf['MSGTYPE_TEXT']:
    #         # 当前只对文本消息进行处理/提取出的地理位置消息也算在内
    #         return
    #
    #     text = trans_coding(msg['text']).encode('utf-8')
    #
    #     uid = msg['raw_msg']['FromUserName']
    #     tid = msg['raw_msg']['ToUserName']
    #
    #     # 在这里可以测试API，添加对于个人消息的自动回复
    #
    #     from_usr = wechat.get_user_by_id(uid)
    #     to_usr = wechat.get_user_by_id(tid)
    #
    #     table_flag = True
    #     table_name = ''
    #     if from_usr['user_flag'] == 0:  # 自己在手机端发送消息
    #         if to_usr['user_flag'] == 2:  # 特殊帐号内容不做记录
    #             table_flag = False
    #         elif to_usr['user_flag'] == 3:  # 未知用户内容，若与公众号聊天但未加其好友可能会出现
    #             table_name = 'unknownz' + trans_unicode_into_int(trans_coding(to_usr['NickName']))
    #         elif to_usr['user_flag'] == 4:  # 公众号内容，服务号也归入其中
    #             table_name = 'publicz' + trans_unicode_into_int(trans_coding(to_usr['NickName']))
    #         elif to_usr['user_flag'] == 1:  # 普通用户
    #             table_name = 'normalz' + trans_unicode_into_int(trans_coding(to_usr['NickName']))
    #         else:
    #             echo('should never in\n')
    #             table_flag = False
    #             pass
    #     elif from_usr['user_flag'] == 2:  # 特殊帐号内容不做记录
    #         table_flag = False
    #     elif from_usr['user_flag'] == 3:
    #         table_name = 'unknownz' + trans_unicode_into_int(trans_coding(from_usr['NickName']))
    #     elif from_usr['user_flag'] == 4:
    #         table_name = 'publicz' + trans_unicode_into_int(trans_coding(from_usr['NickName']))
    #     elif from_usr['user_flag'] == 1:
    #         table_name = 'normalz' + trans_unicode_into_int(trans_coding(from_usr['NickName']))
    #     else:
    #         echo('should never in\n')
    #         table_flag = False
    #         pass
    #
    #     if table_flag:
    #         self.msg_db.create_table(table_name, self.msg_col)  # 如果不存在就会创建表
    #
    #     if uid != wechat.User['UserName']:
    #         if text == 'test_revoke':
    #             dic = wechat.webwxsendmsg('这条消息将被撤回', uid)
    #             wechat.revoke_msg(dic['MsgID'], uid, dic['LocalID'])
    #         elif text == 'reply':
    #             wechat.send_text(uid, '不懂啊')
    #
    #         elif text == 'check_record_count':
    #             if table_flag:
    #                 msg_count = self.msg_db.select_max(table_name, 'MsgOrder')
    #                 echo('接受消息数' + str(msg_count) + '\n')
    #                 wechat.send_text(uid, str(msg_count))
    #             else:
    #                 wechat.send_text(uid, '没有啊!')
    #         elif re.match(r'^check_record_\d+$', text):
    #             msg_order = re.sub(r'^check_record_', '', text)
    #             if table_flag:
    #                 record = self.msg_db.select(table_name, 'MsgOrder', msg_order)
    #                 if record:
    #                     record_msg = 'MsgOrder:' + str(record[0]['MsgOrder']) + ' ' + \
    #                              'Time:' + record[0]['Time'] + ' ' + \
    #                              'From:' + record[0]['FromNick'] + ' ' + \
    #                              'To:' + record[0]['ToNick'] + ' ' + \
    #                              'content:' + record[0]['content']
    #                     echo(record_msg + '\n')
    #                     wechat.send_text(uid, record_msg)
    #                 else:
    #                     echo('no record\n')
    #                     wechat.send_text(uid, '记录无效的！')
    #             else:
    #                 echo('no table\n')
    #                 wechat.send_text(uid, '我们聊过吗？')
    #
    #         # msg记录了接收的消息的全部信息，具体可以将其打印后查看
    #
    #         # 若通过Bot添加自动回复，此处可以调用wechat.bot.xxx_reply
    #
    #         # 可以如同Demo中那样通过链接获取自动回复内容
    #
    #         # 上面可添加测试消息
    #         else:
    #             # 储存非测试消息并自动回复
    #             if table_flag:
    #                 cols = (
    #                     None,
    #                     self.get_time_string(msg['raw_msg']['CreateTime']),
    #                     from_usr['NickName'],
    #                     'myself',
    #                     text
    #                 )
    #                 self.msg_db.insert(table_name, cols)
    #
    #                 flag = False
    #                 if wechat.bot:
    #                     r = wechat.bot.tuling_reply(text, table_name)
    #                     if r:
    #                         echo(r + '\n')
    #                         flag = wechat.send_text(uid, r)
    #                     else:
    #                         pass
    #                     if flag:
    #                         echo('自动回复成功\n')
    #                         reply_cols = (
    #                             None,
    #                             self.get_time_string(),
    #                             'myself',
    #                             from_usr['NickName'],
    #                             r.encode('utf-8')
    #                         )
    #                         self.msg_db.insert(table_name, reply_cols)
    #                     else:
    #                         echo('自动回复失败\n')
    #             else:
    #                 echo('no table\n')
    #     else:
    #         if table_flag:
    #             cols = (
    #                 None,
    #                 self.get_time_string(msg['raw_msg']['CreateTime']),
    #                 'myself',
    #                 to_usr['NickName'],
    #                 text
    #             )
    #             self.msg_db.insert(table_name, cols)
    #         else:
    #             echo('no table\n')
    #
    # def handle_command(self, cmd, msg, group, from_usr, table):
    #     """
    #     @brief      handle msg of `@yourself cmd`
    #     @param      cmd   String    提取的@信息内容
    #     @param      msg   Dict      信息的属性
    #     """
    #     wechat = self.wechat
    #
    #     g_id = group['UserName']
    #
    #     from_id = from_usr['UserName']
    #
    #     if from_id != wechat.User['UserName']:
    #         if cmd == 'runtime':
    #             wechat.send_text(g_id, wechat.get_run_time())
    #         elif cmd == 'test_sendimg':
    #             wechat.send_img(g_id, 'test/emotion/9.jpg')
    #         elif cmd == 'test_sendfile':
    #             wechat.send_file(g_id, 'test/emotion/9.jpg')
    #
    #         elif cmd == 'check_record_count':
    #             msg_count = self.msg_db.select_max(table, 'MsgOrder')
    #             echo('接受消息数' + str(msg_count) + '\n')
    #             wechat.send_text(g_id, str(msg_count))
    #         elif re.match(r'^check_record_\d+$', cmd):
    #             msg_order = re.sub(r'^check_record_', '', cmd)
    #             record = self.msg_db.select(table, 'MsgOrder', msg_order)
    #             if record:
    #                 record_msg = 'MsgOrder:' + str(record[0]['MsgOrder']) + ' ' + \
    #                              'Time:' + record[0]['Time'] + ' ' + \
    #                              'From:' + record[0]['FromNick'] + ' ' + \
    #                              'To:' + record[0]['ToNick'] + ' ' + \
    #                              'content:' + record[0]['content']
    #                 echo(record_msg + '\n')
    #                 wechat.send_text(g_id, record_msg)
    #             else:
    #                 wechat.send_text(g_id, '记录无效的！')
    #
    #         elif re.match(r'^check_m_count_.+$', cmd):
    #             name = re.sub(r'^check_m_count_', '', cmd)
    #             name_code = trans_unicode_into_int(trans_coding(trans_coding(name)))
    #             found = False
    #             for u_type in self.user_type:
    #                 table = u_type + 'z' + name_code
    #                 try:
    #                     msg_count = self.msg_db.select_max(table, 'MsgOrder')
    #                     wechat.send_text(g_id, str(msg_count) + ' type:' + u_type)
    #                     found = True
    #                     break
    #                 except:
    #                     pass
    #             if not found:
    #                 wechat.send_text(g_id, '不认识啊！')
    #         elif re.match(r'^check_m_[0-9]+_[a-z]+_.+$', cmd):
    #             msg_order = re.sub(r'^check_m_', '', cmd).split('_')[0]
    #             usr_type = re.sub(r'^check_m_', '', cmd).split('_')[1]
    #             usr = re.sub(r'^check_m_[0-9]+_[a-z]+_', '', cmd)
    #             usr_n_code = usr_type + 'z' + trans_unicode_into_int(trans_coding(trans_coding(usr)))
    #             try:
    #                 record = self.msg_db.select(usr_n_code, 'MsgOrder', msg_order)
    #                 if record:
    #                     record_msg = 'MsgOrder:' + str(record[0]['MsgOrder']) + ' ' + \
    #                                  'Time:' + record[0]['Time'] + ' ' + \
    #                                  'From:' + record[0]['FromNick'] + ' ' + \
    #                                  'To:' + record[0]['ToNick'] + ' ' + \
    #                                  'content:' + record[0]['content']
    #                     echo(record_msg + '\n')
    #                     wechat.send_text(g_id, record_msg)
    #                 else:
    #                     wechat.send_text(g_id, '记录无效的！')
    #             except:
    #                 wechat.send_text(g_id, '不认识啊！')
    #
    #         # 上面为测试消息
    #         else:
    #             # 储存非测试消息
    #             col = (
    #                 None,
    #                 self.get_time_string(msg['raw_msg']['CreateTime']),
    #                 from_usr['NickName'],
    #                 'Group',
    #                 trans_coding(msg['text']).encode('utf-8')
    #             )
    #             self.msg_db.insert(table, col)
    #
    #             flag = False
    #             if wechat.bot:
    #                 if cmd.strip() == '':
    #                     r = u'@' + trans_coding(from_usr['ShowName']) + u'\u2005' + u'在呢'
    #                     echo(r + u'\n')
    #                     flag = wechat.send_text(g_id, r)
    #                 else:
    #                     t = wechat.bot.tuling_reply(cmd, table)
    #                     if t:
    #                         r = u'@' + trans_coding(from_usr['ShowName']) + u'\u2005' + t
    #                         echo(r + u'\n')
    #                         flag = wechat.send_text(g_id, r)
    #                     else:
    #                         pass
    #                 if flag:
    #                     echo('自动回复成功\n')
    #                     reply_col = (
    #                         None,
    #                         self.get_time_string(),
    #                         wechat.User['NickName'],
    #                         'Group',
    #                         r.encode('utf-8')
    #                     )
    #                     self.msg_db.insert(table, reply_col)
    #                 else:
    #                     echo('自动回复失败\n')

    def check_exit(self):
        total_time = int(time.time() - self.wechat.start_time)
        t = timedelta(seconds=total_time)
        if t.seconds >= 6*60*60:
            return True
        return False
