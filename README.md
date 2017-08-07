# WechatBot project transfer from https://github.com/urinx/weixinbot

https://github.com/tripleha/wechatbot

目录结构:
```bash
.
├── README.md
├── config
│   ├── __init__.py
│   ├── config_manager.py
│   ├── constant.py
│   ├── log.py
│   ├── requirements.txt
│   └── wechat.conf.bak
├── db
│   ├── __init__.py
│   ├── mysql_db.py
│   └── sqlite_db.py
├── docker
│   ├── Dockerfile
│   └── README.md
├── server
│   ├── index.html
│   └── upload.html
├── tmp_data
├── wechat
│   ├── __init__.py
│   ├── utils.py
│   ├── wechat.py
│   ├── wechat_apis.py
│   └── wechat_js_backup
│       └── index_40649b7.js
├── weixin_bot.py
└── wx_handler
    ├── __init__.py
    ├── bot.py
    └── wechat_msg_processor.py
```

2017.8.5

@wechat_apis.py

原代码中发送各类信息的API应该都存在问题（未验证）

已经修改了发送文字信息的API webwxsendmsg() 具体可查看该处注释


@wechat.py

在WeChat.start()后部可以添加定时任务，BOT定时推送功能 可查看该处注释

在WeChat.handle_msg()中指出了添加自动回复的入口（注释


@wechat_msg_processor.py

专门对接收到的信息数据进行处理/数据库操作

在WeChatMsgProcessor.handle_user_msg()中添加对个人聊天信息的自动回复，详见该处注释

在WeChatMsgProcessor.handle_command()中对群聊中的@自己 信息进行自动回复，详见该处注释


@bot.py

对机器人进行功能添加和修改

time_schedule处理定时推送，详见该处注释

reply处理自动回复内容，详见该处注释

内容均通过constant中的链接获取


