# 物联网大赛代码
&emsp;&emsp;wechat文件夹中的为微信小程序代码，server文件夹中为服务器端代码。<br>
&emsp;&emsp;server下app.py为服务器程序代码，config.txt为服务器的nginx配置文件，在服务器的/etc/nginx/sites-available/default里。<br>
&emsp;&emsp;computer文件为电脑端程序。epilepsy_app_new.py是一个带有UI的一键式脚本。可以将实时检测脑电波形发送到服务器，也可以用测试数据绘制脑电波形图并发送到服务器，然后将测试数据发送至开发板，由开发板接收数据并测试，最后通过物联网平台将测试结果和位置信息发送至服务器。