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

    def handle_group_msg(self, msg):
        """
        @brief      Recieve group messages
        @param      msg  Dict: packaged msg
        """
        # rename media files
        for k in ['image', 'video', 'voice']:
            if msg[k]:
                t = time.localtime(float(msg['timestamp']))
                time_str = time.strftime("%Y%m%d%H%M%S", t)
                # format: 时间_消息ID_群名
                file_name = '/%s_%s_%s.' % (time_str, msg['msg_id'], msg['group_name'])
                new_name = re.sub(r'\/\w+\_\d+\.', file_name, msg[k])
                Log.debug('rename file to %s' % new_name)
                os.rename(msg[k], new_name)
                msg[k] = new_name
        # 上面代码功能为重命名群聊接收文件

        # 获取群ID
        if msg['raw_msg']['FromUserName'][:2] == '@@':
            g_id = msg['raw_msg']['FromUserName']
        else:
            g_id = msg['raw_msg']['ToUserName']
        # add new group
        # 貌似此步骤可以省略
        if g_id not in self.wechat.addGroupIDList:
            group = self.wechat.webwxbatchgetcontact([g_id])[0]
            if group:
                self.wechat.addGroupIDList.append(g_id)
                self.wechat.GroupMemeberList['g_id'] = group['MemberList'][:]
                group['MemberList'] = []
                self.wechat.GroupList.append(group)

                # 留做检查用，若出现则说明不应省略此处
                echo('add group in msg handler\n')

        wechat = self.wechat
        if msg['raw_msg']['MsgType'] != wechat.wx_conf['MSGTYPE_TEXT']:
            # 当前只对文本消息进行处理/提取出的地理位置消息也算在内
            return

        # 获取说话者ID
        content = msg['raw_msg']['Content'].replace('&lt;', '<').replace('&gt;', '>')
        from_id = content.split(':<br/>')[0]
        from_usr = wechat.get_group_user_by_id(from_id, g_id)

        # 查看是否创建表
        t_group = wechat.get_group_by_id(g_id)
        if t_group['NickName']:
            table_name = 'groupz' + trans_unicode_into_int(trans_coding(t_group['NickName']))
        else:
            table_name = 'groupz' + trans_unicode_into_int(trans_coding('Group'))
        self.msg_db.create_table(table_name, self.msg_col)

        text = msg['text']
        r = re.findall(u'@[^\u2005]+\u2005', trans_coding(text))
        op_flag = False
        if r and from_id != wechat.User['UserName']:
            usr_self = wechat.get_group_user_by_id(wechat.User['UserName'], g_id)
            for m in r:
                name = m[1:-1].encode('utf-8')
                if name == usr_self['ShowName']:
                    # 进入对于@自己 的消息的处理
                    self.handle_command(re.sub(m, '', trans_coding(text)).encode('utf-8'),
                                        msg, t_group, from_usr, table_name)
                    op_flag = True
                    break
        if not op_flag:
            col = (
                None,
                self.get_time_string(msg['raw_msg']['CreateTime']),
                from_usr['NickName'],
                'Group',
                trans_coding(text).encode('utf-8')
            )
            self.msg_db.insert(table_name, col)

    def handle_user_msg(self, msg):
        """
        @brief      Recieve personal messages
        @param      msg  Dict
        """
        wechat = self.wechat

        if msg['raw_msg']['MsgType'] != wechat.wx_conf['MSGTYPE_TEXT']:
            # 当前只对文本消息进行处理/提取出的地理位置消息也算在内
            return

        text = trans_coding(msg['text']).encode('utf-8')

        uid = msg['raw_msg']['FromUserName']
        tid = msg['raw_msg']['ToUserName']

        # 在这里可以测试API，添加对于个人消息的自动回复

        from_usr = wechat.get_user_by_id(uid)
        to_usr = wechat.get_user_by_id(tid)

        table_flag = True
        table_name = ''
        if from_usr['user_flag'] == 0:  # 自己在手机端发送消息
            if to_usr['user_flag'] == 2:  # 特殊帐号内容不做记录
                table_flag = False
            elif to_usr['user_flag'] == 3:  # 未知用户内容，若与公众号聊天但未加其好友可能会出现
                table_name = 'unknownz' + trans_unicode_into_int(trans_coding(to_usr['NickName']))
            elif to_usr['user_flag'] == 4:  # 公众号内容，服务号也归入其中
                table_name = 'publicz' + trans_unicode_into_int(trans_coding(to_usr['NickName']))
            elif to_usr['user_flag'] == 1:  # 普通用户
                table_name = 'normalz' + trans_unicode_into_int(trans_coding(to_usr['NickName']))
            else:
                echo('should never in\n')
                table_flag = False
                pass
        elif from_usr['user_flag'] == 2:  # 特殊帐号内容不做记录
            table_flag = False
        elif from_usr['user_flag'] == 3:
            table_name = 'unknownz' + trans_unicode_into_int(trans_coding(from_usr['NickName']))
        elif from_usr['user_flag'] == 4:
            table_name = 'publicz' + trans_unicode_into_int(trans_coding(from_usr['NickName']))
        elif from_usr['user_flag'] == 1:
            table_name = 'normalz' + trans_unicode_into_int(trans_coding(from_usr['NickName']))
        else:
            echo('should never in\n')
            table_flag = False
            pass

        if table_flag:
            self.msg_db.create_table(table_name, self.msg_col)  # 如果不存在就会创建表

        if uid != wechat.User['UserName']:
            if text == 'test_revoke':
                dic = wechat.webwxsendmsg('这条消息将被撤回', uid)
                wechat.revoke_msg(dic['MsgID'], uid, dic['LocalID'])
            elif text == 'reply':
                wechat.send_text(uid, '不懂啊')

            elif text == 'check_record_count':
                if table_flag:
                    msg_count = self.msg_db.select_max(table_name, 'MsgOrder')
                    echo('接受消息数' + str(msg_count) + '\n')
                    wechat.send_text(uid, str(msg_count))
                else:
                    wechat.send_text(uid, '没有啊!')
            elif re.match(r'^check_record_\d+$', text):
                msg_order = re.sub(r'^check_record_', '', text)
                if table_flag:
                    record = self.msg_db.select(table_name, 'MsgOrder', msg_order)
                    if record:
                        record_msg = 'MsgOrder:' + str(record[0]['MsgOrder']) + ' ' + \
                                 'Time:' + record[0]['Time'] + ' ' + \
                                 'From:' + record[0]['FromNick'] + ' ' + \
                                 'To:' + record[0]['ToNick'] + ' ' + \
                                 'content:' + record[0]['content']
                        echo(record_msg + '\n')
                        wechat.send_text(uid, record_msg)
                    else:
                        echo('no record\n')
                        wechat.send_text(uid, '记录无效的！')
                else:
                    echo('no table\n')
                    wechat.send_text(uid, '我们聊过吗？')

            # msg记录了接收的消息的全部信息，具体可以将其打印后查看

            # 若通过Bot添加自动回复，此处可以调用wechat.bot.xxx_reply

            # 可以如同Demo中那样通过链接获取自动回复内容

            # 上面可添加测试消息
            else:
                # 储存非测试消息并自动回复
                if table_flag:
                    cols = (
                        None,
                        self.get_time_string(msg['raw_msg']['CreateTime']),
                        from_usr['NickName'],
                        'myself',
                        text
                    )
                    self.msg_db.insert(table_name, cols)

                    flag = False
                    if wechat.bot:
                        r = wechat.bot.tuling_reply(text)
                        if r:
                            echo(r + '\n')
                            flag = wechat.send_text(uid, r)
                        else:
                            pass
                        if flag:
                            echo('自动回复成功\n')
                            reply_cols = (
                                None,
                                self.get_time_string(),
                                'myself',
                                from_usr['NickName'],
                                r.encode('utf-8')
                            )
                            self.msg_db.insert(table_name, reply_cols)
                        else:
                            echo('自动回复失败\n')
                else:
                    echo('no table\n')
        else:
            if table_flag:
                cols = (
                    None,
                    self.get_time_string(msg['raw_msg']['CreateTime']),
                    'myself',
                    to_usr['NickName'],
                    text
                )
                self.msg_db.insert(table_name, cols)
            else:
                echo('no table\n')

    def handle_command(self, cmd, msg, group, from_usr, table):
        """
        @brief      handle msg of `@yourself cmd`
        @param      cmd   String    提取的@信息内容
        @param      msg   Dict      信息的属性
        """
        wechat = self.wechat

        g_id = group['UserName']

        from_id = from_usr['UserName']

        if from_id != wechat.User['UserName']:
            if cmd == 'runtime':
                wechat.send_text(g_id, wechat.get_run_time())
            elif cmd == 'test_sendimg':
                wechat.send_img(g_id, 'test/emotion/9.jpg')
            elif cmd == 'test_sendfile':
                wechat.send_file(g_id, 'test/emotion/9.jpg')

            elif cmd == 'check_record_count':
                msg_count = self.msg_db.select_max(table, 'MsgOrder')
                echo('接受消息数' + str(msg_count) + '\n')
                wechat.send_text(g_id, str(msg_count))
            elif re.match(r'^check_record_\d+$', cmd):
                msg_order = re.sub(r'^check_record_', '', cmd)
                record = self.msg_db.select(table, 'MsgOrder', msg_order)
                if record:
                    record_msg = 'MsgOrder:' + str(record[0]['MsgOrder']) + ' ' + \
                                 'Time:' + record[0]['Time'] + ' ' + \
                                 'From:' + record[0]['FromNick'] + ' ' + \
                                 'To:' + record[0]['ToNick'] + ' ' + \
                                 'content:' + record[0]['content']
                    echo(record_msg + '\n')
                    wechat.send_text(g_id, record_msg)
                else:
                    wechat.send_text(g_id, '记录无效的！')

            elif re.match(r'^check_m_count_.+$', cmd):
                name = re.sub(r'^check_m_count_', '', cmd)
                name_code = trans_unicode_into_int(trans_coding(trans_coding(name)))
                found = False
                for u_type in self.user_type:
                    table = u_type + 'z' + name_code
                    try:
                        msg_count = self.msg_db.select_max(table, 'MsgOrder')
                        wechat.send_text(g_id, str(msg_count) + ' type:' + u_type)
                        found = True
                        break
                    except:
                        pass
                if not found:
                    wechat.send_text(g_id, '不认识啊！')
            elif re.match(r'^check_m_[0-9]+_[a-z]+_.+$', cmd):
                msg_order = re.sub(r'^check_m_', '', cmd).split('_')[0]
                usr_type = re.sub(r'^check_m_', '', cmd).split('_')[1]
                usr = re.sub(r'^check_m_[0-9]+_[a-z]+_', '', cmd)
                usr_n_code = usr_type + 'z' + trans_unicode_into_int(trans_coding(trans_coding(usr)))
                try:
                    record = self.msg_db.select(usr_n_code, 'MsgOrder', msg_order)
                    if record:
                        record_msg = 'MsgOrder:' + str(record[0]['MsgOrder']) + ' ' + \
                                     'Time:' + record[0]['Time'] + ' ' + \
                                     'From:' + record[0]['FromNick'] + ' ' + \
                                     'To:' + record[0]['ToNick'] + ' ' + \
                                     'content:' + record[0]['content']
                        echo(record_msg + '\n')
                        wechat.send_text(g_id, record_msg)
                    else:
                        wechat.send_text(g_id, '记录无效的！')
                except:
                    wechat.send_text(g_id, '不认识啊！')

            # 上面为测试消息
            else:
                # 储存非测试消息
                col = (
                    None,
                    self.get_time_string(msg['raw_msg']['CreateTime']),
                    from_usr['NickName'],
                    'Group',
                    trans_coding(msg['text']).encode('utf-8')
                )
                self.msg_db.insert(table, col)

                flag = False
                if wechat.bot:
                    if cmd.strip() == '':
                        r = '@' + trans_coding(from_usr['ShowName']) + u'\u2005'.encode('utf-8') + '在呢'
                        echo(r + u'\n')
                        flag = wechat.send_text(g_id, r)
                    else:
                        t = wechat.bot.tuling_reply(cmd)
                        if t:
                            r = u'@' + trans_coding(from_usr['ShowName']) + u'\u2005' + t
                            echo(r + u'\n')
                            flag = wechat.send_text(g_id, r)
                        else:
                            pass
                    if flag:
                        echo('自动回复成功\n')
                        reply_col = (
                            None,
                            self.get_time_string(),
                            wechat.User['NickName'],
                            'Group',
                            r.encode('utf-8')
                        )
                        self.msg_db.insert(table, reply_col)
                    else:
                        echo('自动回复失败\n')

    def check_schedule_task(self):
        # 可以添加一些定时函数
        # update group member list at 00:00 am every morning
        t = time.localtime()
        if t.tm_hour == 0 and t.tm_min <= 1:
            Log.debug('update group member list everyday')
            self.wechat.fetch_group_contacts()

