# welcome to https://github.com/tripleha/wechatbot

WechatBot project transfer from https://github.com/urinx/weixinbot
<<<<<<< HEAD

=======
>>>>>>> 85916d4757a0f6757073000e229f3e85cb2fd97d

目录结构:
```
.
├── README.md
├── config
│   ├── __init__.py
│   ├── config_manager.py
│   ├── constant.py
│   ├── log.py
│   ├── requirements.txt
│   └── wechat.conf
├── db
│   ├── __init__.py
│   └── sqlite_db.py
├── test
├── tmp_data
│   └── WeChat.db
├── wechat
│   ├── __init__.py
│   ├── utils.py
│   ├── wechat.py
│   └── wechat_apis.py
├── weixin_bot.py
└── wx_handler
    ├── __init__.py
    ├── bot.py
    └── wechat_msg_processor.py
```
使用说明：

首先需要引入一些第三方库，进入config，输入 pip install -r requirements.txt

返回目录，输入 python weixin_bot.py 即可运行程序

每次启动均需要扫码，断开连接即退出程序，不会保存用户数据到本地，只保存聊天记录到数据库/tmp_data/WeChat.db

聊天机器人功能添加至/wx_handler/bot.py，还需要在/wx_handler/wechat_msg_processor.py中添加调用

数据库内容传输功能可在/wx_handler/wechat_msg_processor.py中添加

其他说明可查看代码注释

更新1.1：

改善了代码结构，在对机器人回复内容进行请求时使用了协程库grequests，考虑到微信服务器对于端口的严格限制，所以在发送回复时并未进行多线程或协程操作。

添加了未测试的同意好友请求功能

命令查看：

check_record_count:查询当前聊天窗口对应的聊天记录数目
check_record_%d:带参数，查询当前聊天窗口的具体某条记录

