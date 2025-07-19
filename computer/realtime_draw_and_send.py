import os
import time
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import base64
import requests
from io import BytesIO
import hashlib
import random

# 配置信息
SERVER_URL = "https://epilepsy.host/api/realtime-upload-waveform"
CLEANUP_URL = "https://epilepsy.host/api/clean-waveform"  # 清理端点
API_KEY = "njunju"
RECORDINGS_DIR = r"C:\Users\Windows\Documents\OpenBCI_GUI\Recordings"
SAMPLE_RATE = 250
PLOT_DURATION = 5  # 每次绘制1秒数据
PLOT_INTERVAL = 1.0  # 每1秒绘制一次波形图并上传
SAMPLE_COUNT = int(SAMPLE_RATE * PLOT_DURATION)  # 500个样本

def get_latest_file():
    """获取最新数据文件路径"""
    sessions = [d for d in os.listdir(RECORDINGS_DIR) 
                if d.startswith("OpenBCISession_")]
    if not sessions:
        return None
    
    # 获取最新会话文件夹
    sessions.sort(key=lambda d: os.path.getmtime(os.path.join(RECORDINGS_DIR, d)), reverse=True)
    latest_session = os.path.join(RECORDINGS_DIR, sessions[0])
    
    # 获取会话中最新的数据文件
    files = [f for f in os.listdir(latest_session) 
             if f.startswith("OpenBCI-RAW-") and f.endswith(".txt")]
    if not files:
        return None
    
    files.sort(key=lambda f: os.path.getmtime(os.path.join(latest_session, f)), reverse=True)
    return os.path.join(latest_session, files[0])

def read_latest_data(file_path, sample_count):
    """读取文件最后sample_count个样本（自动填充不足部分）"""
    try:
        # 读取CSV文件，跳过注释行
        df = pd.read_csv(file_path, comment='%')
        
        # 提取前8个EXG通道数据
        exg_columns = [col for col in df.columns if 'EXG Channel' in col][:8]
        exg_data = df[exg_columns].values
        
        # 处理数据不足的情况
        if len(exg_data) < sample_count:
            # 用第一行数据填充前面
            padding = np.tile(exg_data[0], (sample_count - len(exg_data), 1))
            exg_data = np.vstack([padding, exg_data])
        else:
            exg_data = exg_data[-sample_count:]
            
        return exg_data
    
    except Exception as e:
        print(f"读取数据错误: {str(e)}")
        return None

def plot_waveforms(data):
    """绘制8通道波形图并返回base64编码"""
    plt.figure(figsize=(15, 10))
    time_axis = np.arange(len(data)) / SAMPLE_RATE
    
    for i in range(8):
        plt.subplot(8, 1, i+1)
        plt.plot(time_axis, data[:, i])
        plt.ylabel(f'Ch {i} (μV)')
        plt.grid(True, alpha=0.3)
        
        # 仅在底部通道显示x轴标签
        if i == 7:
            plt.xlabel('Time (s)')
        else:
            plt.tick_params(axis='x', labelbottom=False)
    
    plt.tight_layout()
    
    # 转换为base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100)
    plt.close()
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode('utf-8')

def generate_signature():
    """生成API请求签名"""
    timestamp = str(int(time.time()))
    nonce = str(random.randint(100000, 999999))
    params = [API_KEY, timestamp, nonce]
    params.sort()
    raw_string = ''.join(params)
    signature = hashlib.sha1(raw_string.encode('utf-8')).hexdigest()
    
    return {
        'Signature': signature,
        'Timestamp': timestamp,
        'Nonce': nonce
    }

def upload_waveform(img_base64, user_id):
    """上传波形图到服务器"""
    headers = generate_signature()
    
    payload = {
        "user_id": user_id,
        "waveform_data": img_base64
    }
    
    try:
        response = requests.post(
            SERVER_URL,
            json=payload,
            headers=headers,
            timeout=4
        )
        
        if response.status_code == 200:
            print(f"波形图上传成功! 时间: {time.strftime('%H:%M:%S')}")
        else:
            print(f"上传失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"上传异常: {str(e)}")

def initialize_cleanup(user_id):
    """在开始前清理服务器上的旧数据"""
    headers = generate_signature()
    
    payload = {
        "user_id": user_id
    }
    
    print(f"正在初始化清理用户 {user_id} 的服务器数据...")
    
    try:
        response = requests.post(
            CLEANUP_URL,
            json=payload,
            headers=headers,
            timeout=5
        )
        
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get('success'):
                deleted_count = res_data.get('deleted_count', 0)
                print(f"✅ 清理成功! 已删除 {deleted_count} 条记录")
                return True
            else:
                print(f"清理失败: {res_data.get('message', '未知错误')}")
        else:
            print(f"清理请求失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"清理请求异常: {str(e)}")
    
    return False

def main():
    """主循环"""
    user_id = input("请输入用户ID: ").strip()
    
    # 新增：在开始前清理服务器数据
    if not initialize_cleanup(user_id):
        confirm = input("服务器清理失败，是否继续? (y/n): ").strip().lower()
        if confirm != 'y':
            print("程序已终止")
            return
    
    print("开始实时脑电监测...")
    
    while True:
        start_time = time.time()
        
        # 获取最新文件
        current_file = get_latest_file()
        if not current_file:
            print("未找到有效数据文件")
            time.sleep(PLOT_INTERVAL)
            continue
        
        # 读取数据
        data = read_latest_data(current_file, SAMPLE_COUNT)
        if data is None:
            print("数据读取失败")
            time.sleep(PLOT_INTERVAL)
            continue
        
        # 绘图并上传
        img_base64 = plot_waveforms(data)
        upload_waveform(img_base64, user_id)
        
        # 确保精确的时间间隔
        elapsed = time.time() - start_time
        print(f"绘图和上传耗时: {elapsed:.2f}秒")
        sleep_time = max(0, PLOT_INTERVAL - elapsed)
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()