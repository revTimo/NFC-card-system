#!/usr/bin/python
# -*- coding: utf-8 -*-

import wx
import wx.lib.newevent
import nfc
import threading
from binascii import hexlify
import requests
import json
import binascii
import time

(ShowCardEvent, SHOW_CARD_EVENT) = wx.lib.newevent.NewEvent()
(GoneCardEvent, GONE_CARD_EVENT) = wx.lib.newevent.NewEvent()
# edyカードのPMM
edy_pmm = '0120220427674eff'

class TagReader(threading.Thread):

    def __init__(self, wx_frame):
        super(TagReader, self).__init__(name='TagReader')
        self.terminate = False
        self.wx_frame = wx_frame

    def run(self):
        clf = nfc.ContactlessFrontend('usb')
        rdwr_options = {'on-connect': self.on_tag_connect,
                        'on-release': self.on_tag_release}
        while not self.terminate:
            clf.connect(rdwr=rdwr_options, terminate=lambda : \
                        self.terminate)

    def on_tag_connect(self, tag):
       # type3以外の場合
        if tag.type != 'Type3Tag':
            return

       # 異なるカードエラー処理
        current_card_pmm = binascii.hexlify(tag.pmm)
        if current_card_pmm != edy_pmm:
            return

        (idm, pmm) = tag.polling(system_code=0xFE00)
        (tag.idm, tag.pmm, tag.sys) = (idm, pmm, 0xFE00)

       # 68 => random service
        service_code = nfc.tag.tt3.ServiceCode(68, 0x110b)
        block_code = nfc.tag.tt3.BlockCode(0, service=0)
        data = tag.read_without_encryption([service_code], [block_code])
        service_return_data = hexlify(data)

       # edy番号だけをカットする
        edy_num = service_return_data[4:20]

       # request post 送信
        headers = {'content-type': 'application/json'}
        url = \
            'https://www.pi-pe.co.jp/api/service/custom_program/run/request'
        post_data = \
            'spiral_api_token=00011BJhzZAH816d6a60edcb092d078555377b47f8454a62a55e&title=tc_register&arg=register&arg=' \
            + edy_num
        result = requests.post(url, params=post_data, headers=headers)
        wx.PostEvent(self.wx_frame, ShowCardEvent(msg=result.text))
        return True

    def on_tag_release(self, tag):
        #カードをreleaseのときメッセージがすぐ消えない1秒待ち
        time.sleep(1)
        wx.PostEvent(self.wx_frame, GoneCardEvent())


class Frame(wx.Frame):

    def __init__(self, title):

        # frame作成
        super(Frame, self).__init__(None, title=title, size=(700, 500))

        #親panel
        topPanel = wx.Panel(self)
        panel1 = wx.Panel(topPanel, -1, pos=(0,5),size=(200,130))
        self.image = wx.Image('image/logo.gif')
        bitmap = self.image.ConvertToBitmap()
        wx.StaticBitmap(panel1, -1, bitmap, pos=(0,0), size=self.image.GetSize())

        # テキストpanel
        self.text = wx.StaticText(topPanel, pos=(40, 180))
        font = wx.Font(30, wx.DECORATIVE, wx.NORMAL, wx.NORMAL)
        self.text.SetFont(font)

        # touch handler呼び出す
        self.Bind(SHOW_CARD_EVENT, self.show_card_event)

        # release handler呼び出す
        self.Bind(GONE_CARD_EVENT, self.gone_card_event)
        self.Bind(wx.EVT_CLOSE, self.close_window_event)
        wx.PostEvent(self, GoneCardEvent())
                
        # アプリicon
        icon = wx.EmptyIcon()
        icon.CopyFromBitmap(wx.Bitmap('image/raspberry.png', wx.BITMAP_TYPE_ANY))
        self.SetIcon(icon)
        self.Show()

    def close_window_event(self, event):
        self.Destroy()

    def show_card_event(self, event):
        # return message を表示させる
        return_data = json.loads(event.msg)
        start_time = return_data['start_date']
        greeting = (return_data['output'])[0:10]
        stuff_name = (return_data['output'])[10:-11]
        register_msg = (return_data['output'])[-11:]
        self.text.SetLabel(start_time + '\n' + greeting + '\n'
                           + stuff_name + '\n' + register_msg)

    def gone_card_event(self, event):
        self.text.SetLabel("セキュリティカードをかざして\nください")


app = wx.App()
reader = TagReader(Frame('勤怠システム'))
reader.start()
app.MainLoop()
reader.terminate = True  # tell the reader to terminate
reader.join()  # and wait for the reader thread to finish
