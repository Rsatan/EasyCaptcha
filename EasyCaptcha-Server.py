#!/usr/bin/env python
# -*- conding:utf-8 -*-
from http.server import HTTPServer, BaseHTTPRequestHandler
import re,time,base64,os,requests
import json
from urllib.parse import parse_qs
import onnxruntime
import torch
from PIL import Image
import torchvision.transforms as transforms
import numpy as np


host = ('0.0.0.0', 8899)
count = 50 #保存多少个验证码及结果
captcha_array = list("0123456789+-×÷=？")
captcha_size = 5


def vec2Text(vec):
    vec = torch.argmax(vec, dim=1)  # 把为1的取出来
    text = ''
    for i in vec:
        text += captcha_array[i]
    return text


def to_numpy(tensor):
    return tensor.detach().cpu().numpy() if tensor.requires_grad else tensor.cpu().numpy()


def send_request(url, data_package):
    # 判断是否为 GET 或 POST 请求
    if data_package.startswith("GET") or data_package.startswith("get"):
        method = "GET"
        data = None  # GET 请求通常没有请求体
        headers = {}
        body_start_index = data_package.find("\n\n")
        if body_start_index == -1:
            body_start_index = data_package.find("\r\n\r\n")
        if body_start_index == -1:
            body_start_index = len(data_package)

        headers_lines = data_package[:body_start_index].strip().split("\n")
        for line in headers_lines[1:]:
            key, value = line.split(": ", 1)
            headers[key] = value

    elif data_package.startswith("POST") or data_package.startswith("post"):
        method = "POST"

        # 解析 headers 和 body
        headers = {}
        body_start_index = data_package.find("\n\n")
        if body_start_index == -1:
            body_start_index = data_package.find("\r\n\r\n")
        if body_start_index == -1:
            body_start_index = len(data_package)

        headers_lines = data_package[:body_start_index].strip().split("\n")
        for line in headers_lines[1:]:
            key, value = line.split(": ", 1)
            headers[key] = value

        data = data_package[body_start_index + 2:].strip()

    else:
        raise ValueError("不支持的请求类型")

    # 根据方法发送请求
    if method == "GET":
        response = requests.get(url, headers=headers,timeout=3,verify=False)
    elif method == "POST":
        response = requests.post(url, headers=headers, data=data,timeout=3,verify=False)

    return response

class Resquest(BaseHTTPRequestHandler):
    def handler(self):
        print("data:", self.rfile.readline().decode())
        self.wfile.write(self.rfile.readline())

    def do_GET(self):
        print(self.requestline)
        if self.path != '/':
            self.send_error(404, "Page not Found!")
            return
        with open('temp/log.txt', 'r') as f:
            content = f.read()
        data = f'''
<title>EasyCaptcha</title>
<style>
    body {{
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background-color: #f9f7ff;
        color: #343a40;
        text-align: center;
        margin: 0;
        padding: 20px;
    }}
    h1 {{
        font-size: 2em;
        margin-bottom: 20px;
        color: #8a7bca; 
    }}
    p,a {{
        color: #8a7bca; 
        text-decoration: none;
        font-weight: bold;
    }}
    a:hover {{
        text-decoration: underline;
    }}
    table {{
        width: 80%;
        margin: 20px auto;
        border-collapse: collapse;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        border-radius: 8px;
        overflow: hidden;
    }}
    th, td {{
        padding: 15px;
        text-align: center;
    }}
    th {{
        background-color: #8a7bca;
        color: white;
        font-size: 1.2em;
    }}
    tr:nth-child(even) {{
        background-color: #f2e9ff;
    }}
    tr:hover {{
        background-color: #e0d3ff;
    }}
    img {{
        max-width: 150px; 
        height: auto;
        border-radius: 10px;
        object-fit: cover;
    }}
    td {{
        vertical-align: middle; 
    }}
</style>
<body>
    <h1>EasyCaptcha</h1>
    <p>author: <a href="https:blog.rsa7an.top">Rsa7an</a> ｜ <a href="http://www.nmd5.com">算命縖子</a></p>
    <table>
        <tr>
            <th>验证码</th>
            <th>识别结果</th>
            <th>时间</th>
            <th>验证码模块</th>
        </tr>
        {content}
    </table>
</body>
'''


        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=UTF-8')
        self.end_headers()
        self.wfile.write(data.encode())

    def do_POST(self):
        #print(self.headers)
        #print(self.command)
        text = ''
        re_data =""
        EasyCaptcha_url =""
        EasyCaptcha_type = ""
        EasyCaptcha_cookie = ""
        EasyCaptcha_set_ranges = ""
        EasyCaptcha_complex_request = ""
        EasyCaptcha_rf = ""
        EasyCaptcha_re = ""
        EasyCaptcha_is_re_run = ""

        try:
            if self.path != '/base64' and self.path != '/imgurl':
                self.send_error(404, "Page not Found!")
                return

            if self.path == '/base64':
                #预留接口
                self.send_error(404, "Page not Found!")
                return

            elif self.path == '/imgurl':
                img_name = time.time()
                req_datas = self.rfile.read(int(self.headers['content-length']))
                req_datas = req_datas.decode()
                # 转化为json格式
                json_req_datas = {k: v[0] for k, v in parse_qs(req_datas).items()}
                # EasyCaptcha_url ： url（base64）
                # EasyCaptcha_type ：模式（1普通、2复杂）
                # EasyCaptcha_cookie：cookie（base64）
                # EasyCaptcha_set_ranges：验证码输出模式
                # EasyCaptcha_complex_request：复杂模式的验证码请求包（base64）
                # EasyCaptcha_rf：高级模式 - 数据来源（响应头1 / 体0）
                # EasyCaptcha_re：高级模式 - 正则（base64）
                # EasyCaptcha_is_re_run：高级模式 - 按钮（启动true / 关闭false）

                EasyCaptcha_url = base64.b64decode(json_req_datas["EasyCaptcha_url"]).decode("utf-8")
                EasyCaptcha_type = json_req_datas["EasyCaptcha_type"]
                EasyCaptcha_cookie = base64.b64decode(json_req_datas["EasyCaptcha_cookie"]).decode("utf-8")
                EasyCaptcha_set_ranges = json_req_datas["EasyCaptcha_set_ranges"]
                EasyCaptcha_complex_request = base64.b64decode(json_req_datas["EasyCaptcha_complex_request"]).decode("utf-8")
                EasyCaptcha_rf = json_req_datas["EasyCaptcha_rf"]
                EasyCaptcha_re = base64.b64decode(json_req_datas["EasyCaptcha_re"]).decode("utf-8")
                EasyCaptcha_is_re_run = json_req_datas["EasyCaptcha_is_re_run"]

                try:
                    if EasyCaptcha_type == "1":

                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36",
                            "Referer":"https://www.baidu.com",
                            "Cookie": EasyCaptcha_cookie}
                        print("\n\n"+EasyCaptcha_url)
                        #print(headers)
                        request = requests.get(EasyCaptcha_url,headers=headers,timeout=3,verify=False)
                    elif EasyCaptcha_type == "2":
                        request = send_request(EasyCaptcha_url,EasyCaptcha_complex_request)

                    CAPTCHA = request.text# 获取图片

                    print("图片地址响应码：",request.status_code)

                    if EasyCaptcha_is_re_run == "true":#判断是否启用高级模式
                        try:
                            if EasyCaptcha_rf == '0':
                                #请求体数据
                                re_data = re.findall(EasyCaptcha_re,CAPTCHA)[0]
                                print("正则匹配结果："+re_data)
                            elif EasyCaptcha_rf == '1':
                                #请求头数据
                                rp_head = EasyCaptcha_re.split("|")
                                head_key = rp_head[0]
                                re_zz = EasyCaptcha_re[len(head_key)+1:]
                                re_data = re.findall(re_zz, request.headers[head_key])[0]
                                print("正则匹配结果：" + re_data)
                        except:
                            re_data = " regex match error!!\n\n"

                    if EasyCaptcha_set_ranges=="9" :#不识别验证码，验证码在返回包的情况
                        text += "0000|" + re_data
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(text.encode('utf-8'))
                        return

                    # 判断验证码数据包是否为json格式
                    if re.findall('"\s*:\s*.?"', CAPTCHA):
                        print("json格式")
                        CAPTCHA = CAPTCHA.split('"')
                        CAPTCHA.sort(key=lambda i: len(i), reverse=True)  # 按照字符串长度排序
                        CAPTCHA = CAPTCHA[0].split(',')
                        CAPTCHA.sort(key=lambda i: len(i), reverse=True)  # 按照字符串长度排序
                        CAPTCHA_base64 = CAPTCHA[0]
                        text_img = False
                    elif re.findall('data:image/\D*;base64,', CAPTCHA):
                        print("base64格式")
                        CAPTCHA = CAPTCHA.split(',')
                        CAPTCHA.sort(key=lambda i: len(i), reverse=True)  # 按照字符串长度排序
                        CAPTCHA_base64 = CAPTCHA[0]
                        text_img = False
                    else:
                        print("图片格式")
                        text_img = True

                    if text_img:
                        #图片格式直接保存
                        with open("temp/%s.png" % img_name, 'wb') as f:
                            f.write(request.content)
                            f.close()
                    else:
                        #base64需要解码保存
                        with open("temp/%s.png" % img_name, 'wb') as f:
                            f.write(base64.b64decode(CAPTCHA_base64))
                            f.close()

                except:
                    print("\n\n" + EasyCaptcha_url)
                    print("error:获取图片出错！")

            # 验证码识别 ddddocr
            if EasyCaptcha_set_ranges == "8":
                onnxFile = './model/RuoyiCaptcha.onnx'
                img = Image.open(r"temp/%s.png" % img_name)
                trans = transforms.Compose([
                    transforms.Resize((60, 160)),
                    transforms.ToTensor()
                ])
                img_tensor = trans(img)
                img_tensor = img_tensor.reshape(1, 3, 60, 160)  # 1张图片 1 灰色
                ort_session = onnxruntime.InferenceSession(onnxFile)
                modelInputName = ort_session.get_inputs()[0].name
                # onnx 网络输出
                onnx_out = ort_session.run(None, {modelInputName: to_numpy(img_tensor)})
                onnx_out = torch.tensor(np.array(onnx_out))
                onnx_out = onnx_out.view(-1, captcha_array.__len__())
                text = vec2Text(onnx_out)[:-2]
                text = text.replace('×', '*')
                text = text.replace('÷', '/')
                print('\n识别的结果:', text)  # 输出识别结果
                #计算结果不保留小数
                text = str(int(eval(text)))
                print('\n计算结果:', text, '\n')  # 输出识别结果
            else:
                ocr.set_ranges(int(EasyCaptcha_set_ranges))  # 设置输出格式
                with open(r"temp/%s.png" % img_name, "rb") as f:
                    img_bytes = f.read()

                result_text = ocr.classification(img_bytes, probability=True)
                text = ""
                for i in result_text['probability']:
                    text += result_text['charsets'][i.index(max(i))]
                print('\n' + text + '\n')  # 输出识别结果



            #保存最新count个的验证码及识别结果
            with open('temp/log.txt', 'r') as f:
                data = ""
                counts = 0
                content = f.read()
                pattern = re.compile(r'.*?\n')
                result1 = pattern.findall(content)
                for i in result1:
                    counts += 1
                    if counts >= count: break
                    data = data + i
            with open("temp/%s.png" % img_name, 'rb') as f:
                base64_img = base64.b64encode(f.read()).decode("utf-8")
            with open('temp/log.txt', 'w') as f:
                f.write('<tr align=center><td><img src="data:image/png;base64,%s"/></td><td>%s</td><td>%s</td><td>%s</td></tr>\n'%(base64_img,text,time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(img_name))),EasyCaptcha_type)+ data)

            #删除掉图片文件，以防占用太大的内存
            os.remove("temp/%s.png"%img_name)
        except Exception as e:
            print(e)
            text= '0000'
            print("\n\n" + EasyCaptcha_url)
            print('\nerror:识别失败！\n')
        
        if text =='':
            text= '0000'
            print('\n识别失败！\n')

        if EasyCaptcha_is_re_run == "true":
            text += "|" + re_data

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(text.encode('utf-8'))

if __name__ == '__main__':
    print('Loading ddddocr...')
    import ddddocr
    os.makedirs('temp', exist_ok=True)
    with open('temp/log.txt', 'w') as f:
        pass
    server = HTTPServer(host, Resquest)
    print("=========================================================")
    print('''
  ______                 _____            _       _           
 |  ____|               / ____|          | |     | |          
 | |__   __ _ ___ _   _| |     __ _ _ __ | |_ ___| |__   __ _ 
 |  __| / _` / __| | | | |    / _` | '_ \| __/ __| '_ \ / _` |
 | |___| (_| \__ \ |_| | |___| (_| | |_) | || (__| | | | (_| |
 |______\__,_|___/\__, |\_____\__,_| .__/ \__\___|_| |_|\__,_|
                   __/ |           | |                        
                  |___/            |_|            author: 算命縖子 ｜ Rsa7an            
''')
    print("=========================================================")
    print("Starting server, listen at: %s:%s" % host)
    print('Loading complete! Please visit: http://127.0.0.1:%s\n\n\n' % host[1])
    ocr = ddddocr.DdddOcr(show_ad=False)
    server.serve_forever()