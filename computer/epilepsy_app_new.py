"""
癫痫脑电数据分析系统
功能：
1. 实时脑电监测：自动读取OpenBCI设备生成的脑电数据，进行滤波处理并上传波形图
2. 离线数据分析：处理HDF5格式的脑电数据文件，生成波形图并传输到服务器
3. 用户界面：基于tkinter和ttkbootstrap的图形界面，支持日志查看和状态监控

主要技术组件：
- 实时数据监控线程：定期读取最新脑电数据
- Butterworth低通滤波器：滤除30Hz以上高频噪声
- 数据可视化：Matplotlib绘制8通道脑电波形
- API安全机制：基于时间戳和SHA1的请求签名验证
- 网络传输：HTTP API上传+TCP套接字文件传输
"""

# 基础库导入
import requests  # HTTP请求库
import base64    # 二进制数据编码
import matplotlib # 绘图库
matplotlib.use('Agg')  # 设置非交互式后端，避免GUI冲突
import matplotlib.pyplot as plt  # 绘图接口
from io import BytesIO  # 内存二进制流处理
import numpy as np  # 数值计算
import h5py  # HDF5文件处理
import time  # 时间操作
import hashlib  # 哈希算法
import random  # 随机数生成
import socket  # 网络套接字
import os  # 操作系统接口
import threading  # 多线程支持
import sys  # 系统参数

# GUI组件
from tkinter import scrolledtext  # 滚动文本框
import tkinter as tk  # GUI基础库
from tkinter import ttk, filedialog, messagebox  # 高级GUI组件
from ttkbootstrap import Style  # 界面主题美化

# 数据处理
import pandas as pd  # 数据分析
from scipy import signal  # 信号处理

# ===================== 全局配置 =====================
SERVER_URL = "https://epilepsy.host"  # 服务器基础地址
API_KEY = "njunju"  # API认证密钥，需与服务器端IOT_PLATFORM_TOKEN一致

# 实时监测参数配置
REALTIME_RECORDINGS_DIR = r"C:\Users\Windows\Documents\OpenBCI_GUI\Recordings"  # OpenBCI数据存储路径
REALTIME_SAMPLE_RATE = 250  # 采样率 (Hz)
REALTIME_PLOT_DURATION = 5  # 单次波形图时间跨度 (秒)
REALTIME_PLOT_INTERVAL = 5.0  # 绘图/上传间隔 (秒)
REALTIME_SAMPLE_COUNT = int(REALTIME_SAMPLE_RATE * REALTIME_PLOT_DURATION)  # 单次处理样本数
REALTIME_CUTOFF_FREQ = 50.0  # 低通滤波截止频率 (Hz)
REALTIME_CLEANUP_URL = f"{SERVER_URL}/api/clean-waveform"  # 服务器数据清理接口

# ===================== 实时监测核心类 =====================
class RealTimeMonitor:
    """实时脑电监测引擎，包含数据采集、处理、上传全流程"""
    
    def __init__(self, user_id, log_callback, status_callback):
        """
        初始化实时监测器
        :param user_id: 用户唯一标识
        :param log_callback: 日志回调函数
        :param status_callback: 状态更新回调函数
        """
        self.user_id = user_id
        self.log_callback = log_callback  # 日志输出回调
        self.status_callback = status_callback  # 状态更新回调
        self.running = False  # 运行状态标志
        self.monitor_thread = None  # 监控线程句柄
        
    def log(self, message):
        """日志记录方法（通过回调传递到GUI）"""
        if self.log_callback:
            self.log_callback(message)
            
    def update_status(self, status):
        """状态更新方法（通过回调传递到GUI）"""
        if self.status_callback:
            self.status_callback(status)
    
    def butter_lowpass_filter(self, data, cutoff, fs, order=4):
        """
        Butterworth低通滤波器实现
        :param data: 原始信号数据
        :param cutoff: 截止频率 (Hz)
        :param fs: 采样频率 (Hz)
        :param order: 滤波器阶数
        :return: 滤波后的信号
        """
        nyq = 0.5 * fs  # 奈奎斯特频率
        normal_cutoff = cutoff / nyq  # 归一化截止频率
        # 设计滤波器系数
        b, a = signal.butter(order, normal_cutoff, btype='low', analog=False)
        # 零相位滤波 (filtfilt避免相位失真)
        y = signal.filtfilt(b, a, data)
        return y

    def get_latest_file(self):
        """获取OpenBCI最新数据文件路径"""
        # 扫描会话目录 (格式: OpenBCISession_*)
        sessions = [d for d in os.listdir(REALTIME_RECORDINGS_DIR) 
                    if d.startswith("OpenBCISession_")]
        if not sessions:
            return None
        
        # 按修改时间排序获取最新会话
        sessions.sort(key=lambda d: os.path.getmtime(os.path.join(REALTIME_RECORDINGS_DIR, d)), reverse=True)
        latest_session = os.path.join(REALTIME_RECORDINGS_DIR, sessions[0])
        
        # 获取会话中的最新数据文件 (格式: OpenBCI-RAW-*.txt)
        files = [f for f in os.listdir(latest_session) 
                 if f.startswith("OpenBCI-RAW-") and f.endswith(".txt")]
        if not files:
            return None
        
        # 按修改时间排序获取最新文件
        files.sort(key=lambda f: os.path.getmtime(os.path.join(latest_session, f)), reverse=True)
        return os.path.join(latest_session, files[0])

    def read_latest_data(self, file_path, sample_count):
        """
        读取并预处理脑电数据
        :param file_path: 数据文件路径
        :param sample_count: 需要读取的样本数量
        :return: 8通道滤波后的脑电数据 (numpy数组)
        """
        try:
            # 使用pandas读取CSV，忽略注释行 (%开头)
            df = pd.read_csv(file_path, comment='%')
            
            # 提取前8个EXG通道 (脑电通道)
            exg_columns = [col for col in df.columns if 'EXG Channel' in col][:8]
            exg_data = df[exg_columns].values
            #nan_count = np.isnan(exg_data).sum()
            #if nan_count > 0:
            #    #self.log(f"警告：发现{nan_count}个NaN值，正在清理...")
            #    print(f"警告：exg_data1发现{nan_count}个NaN值")
            
            # 处理数据不足的情况 (用首行数据向前填充)
            if len(exg_data) < sample_count:
                padding = np.tile(exg_data[0], (sample_count - len(exg_data), 1))
                exg_data = np.vstack([padding, exg_data])
            else:
                exg_data = exg_data[-sample_count:]
                
                
            # 对于每个通道，检查有没有nan。如果有，则从该通道末尾开始向前找第一个非nan值。然后从头遍历整个通道，将nan值替换为该非nan值。
            # 如果全部都是nan，也就是找不到非nan值，则将该通道全部替换为0。
            # === 新增：按照要求处理NaN值 ===
            # 遍历每个通道
            for channel_idx in range(8):
                channel_data = exg_data[:, channel_idx]

                # 检查当前通道的NaN情况
                nan_mask = np.isnan(channel_data)
                nan_count = np.sum(nan_mask)

                if nan_count > 0:
                    # 打印警告信息
                    print(f"警告：通道 {channel_idx} 发现 {nan_count} 个NaN值")

                    # 情况1：整个通道都是NaN
                    if nan_count == len(channel_data):
                        print(f"通道 {channel_idx} 全部为NaN，已替换为0")
                        exg_data[:, channel_idx] = 0

                    # 情况2：部分NaN
                    else:
                        # 从末尾向前找到第一个非NaN值
                        last_valid_value = None
                        for i in range(len(channel_data)-1, -1, -1):
                            if not np.isnan(channel_data[i]):
                                last_valid_value = channel_data[i]
                                break
                            
                        # 如果找到有效值，用该值填充所有NaN
                        if last_valid_value is not None:
                            channel_data[nan_mask] = last_valid_value
                            exg_data[:, channel_idx] = channel_data
                            print(f"通道 {channel_idx} 的NaN值已用最后有效值 {last_valid_value:.2f} 填充")
                        else:
                            # 极端情况：没找到有效值，全部设为0
                            exg_data[:, channel_idx] = 0
                            print(f"通道 {channel_idx} 未找到有效值，已全部替换为0")
        
            # 打印处理后的数据信息
            #print(f"读取数据形状: {exg_data.shape} (样本数: {len(exg_data)}, 通道数: {exg_data.shape[1]})")  
            
            
            # 应用低通滤波器到每个通道
            filtered_data = exg_data.copy()
            for i in range(8):
                filtered_data[:, i] = self.butter_lowpass_filter(
                    filtered_data[:, i], 
                    REALTIME_CUTOFF_FREQ, 
                    REALTIME_SAMPLE_RATE
                )
            # 舍弃前30个滤波不稳定样本
            filtered_data = filtered_data[30:]
            
            # 打印滤波后数据形状
            #print(f"滤波后数据形状: {filtered_data.shape} (样本数: {len(filtered_data)}, 通道数: {filtered_data.shape[1]})")
            # 打印滤波后数据全部内容
            #for i in range(8):
            #    print(f"滤波后 Ch{i} 数据: {filtered_data[:, i]}")
            return filtered_data
        
        except Exception as e:
            self.log(f"数据读取错误: {str(e)}")
            return None

    def plot_waveforms(self, data):
        """
        绘制8通道脑电波形图
        :param data: 形状为(N, 8)的脑电数据
        :return: base64编码的PNG图像
        """
        # 创建15x10英寸画布
        plt.figure(figsize=(15, 18))
        # 生成时间轴 (秒)
        time_axis = np.arange(len(data)) / REALTIME_SAMPLE_RATE
        
        height_max = 0
        for i in range(8):
            y_min = data[:, i].min()
            y_max = data[:, i].max()
            height = y_max - y_min
            if height > height_max:
                height_max = height

        # 绘制8个子图 (每通道一个)
        for i in range(8):
            mean = data[:, i].mean()
            y_min = mean - height_max / 3 * 5
            y_max = mean + height_max / 3 * 5
            plt.subplot(8, 1, i+1)  # 8行1列布局
            plt.plot(time_axis, data[:, i])  # 绘制时域波形
            plt.ylabel(f'Ch {i} (μV)')  # Y轴标签
            plt.grid(True, alpha=0.3)  # 半透明网格
            plt.ylim(y_min, y_max)
            
            # 仅底部子图显示X轴
            if i == 7:
                plt.xlabel('Time (s)')
            else:
                plt.tick_params(axis='x', labelbottom=False)  # 隐藏X轴标签
        
        plt.tight_layout()  # 自动调整子图间距
        
        # 将图像保存到内存缓冲区
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=100)
        plt.close()
        buffer.seek(0)
        # 返回base64编码字符串
        return base64.b64encode(buffer.read()).decode('utf-8')

    def generate_signature(self):
        """
        生成API请求签名 (防重放攻击)
        算法: SHA1(API_KEY + Timestamp + Nonce) 按字母排序后拼接
        :return: 包含签名参数的字典
        """
        timestamp = str(int(time.time()))  # 当前时间戳
        nonce = str(random.randint(100000, 999999))  # 随机数
        params = [API_KEY, timestamp, nonce]
        params.sort()  # 参数排序
        raw_string = ''.join(params)  # 拼接字符串
        signature = hashlib.sha1(raw_string.encode('utf-8')).hexdigest()  # SHA1哈希
        
        return {
            'Signature': signature,
            'Timestamp': timestamp,
            'Nonce': nonce
        }

    def upload_waveform(self, img_base64):
        """
        上传波形图到服务器
        :param img_base64: base64编码的图像数据
        :return: 上传成功返回True, 否则False
        """
        # 生成API签名头
        headers = self.generate_signature()
        
        # 构建JSON负载
        payload = {
            "user_id": self.user_id,
            "waveform_data": img_base64
        }
        
        try:
            # 发送POST请求到实时上传接口
            response = requests.post(
                f"{SERVER_URL}/api/realtime-upload-waveform",
                json=payload,
                headers=headers,
                timeout=5  # 5秒超时
            )
            
            if response.status_code == 200:
                self.log(f"波形图上传成功! 时间: {time.strftime('%H:%M:%S')}")
                return True
            else:
                self.log(f"上传失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.log(f"上传异常: {str(e)}")
            return False

    def initialize_cleanup(self):
        """初始化时清理服务器上的旧数据"""
        headers = self.generate_signature()
        payload = {"user_id": self.user_id}
        
        self.log(f"初始化清理用户 {self.user_id} 的服务器数据...")
        
        try:
            # 发送清理请求
            response = requests.post(
                REALTIME_CLEANUP_URL,
                json=payload,
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get('success'):
                    deleted_count = res_data.get('deleted_count', 0)
                    self.log(f"✅ 清理成功! 已删除 {deleted_count} 条记录")
                    return True
                else:
                    self.log(f"清理失败: {res_data.get('message', '未知错误')}")
            else:
                self.log(f"清理请求失败: {response.status_code} - {response.text}")
        except Exception as e:
            self.log(f"清理请求异常: {str(e)}")
        
        return False

    def start(self):
        """启动实时监测服务"""
        if self.running:
            self.log("实时监测已运行")
            return
            
        # 服务器数据清理
        if not self.initialize_cleanup():
            self.log("警告：服务器清理失败")
            
        self.running = True
        # 创建守护线程运行监控循环
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.update_status("实时监测运行中")
        self.log("实时脑电监测已启动")
        
    def stop(self):
        """停止实时监测服务"""
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(2.0)  # 等待线程结束
        self.update_status("实时监测已停止")
        self.log("实时脑电监测已停止")
        
    def _monitor_loop(self):
        """实时监测主循环"""
        self.log("开始实时脑电监测...")
        
        # 1. 获取最新数据文件
        current_file = self.get_latest_file()
        if not current_file:
            self.log("未找到有效数据文件")
            print("请确保OpenBCI设备已连接并生成数据")
            return
        
        while self.running:
            start_time = time.time()  # 循环起始时间
            
            # 2. 读取并预处理数据
            data = self.read_latest_data(current_file, REALTIME_SAMPLE_COUNT)
            if data is None:
                self.log("数据读取失败")
                time.sleep(REALTIME_PLOT_INTERVAL)
                continue
            
            # 3. 生成波形图并上传
            img_base64 = self.plot_waveforms(data)
            self.upload_waveform(img_base64)
            
            # 4. 计算并调整等待时间
            elapsed = time.time() - start_time
            self.log(f"绘图和上传耗时: {elapsed:.2f}秒")
            sleep_time = max(0, REALTIME_PLOT_INTERVAL - elapsed)
            time.sleep(sleep_time)  # 维持固定间隔

# ===================== 主应用GUI类 =====================
class EpilepsyApp:
    """癫痫脑电分析系统GUI主类"""
    
    def __init__(self, root):
        """
        初始化GUI界面
        :param root: Tk根窗口
        """
        self.root = root
        self.root.title("癫痫脑电数据分析系统")
        self.root.geometry("1000x700")  # 初始窗口尺寸
        
        # 应用ttkbootstrap主题 (cosmo风格)
        self.style = Style(theme='cosmo')
        
        # 主框架
        self.main_frame = ttk.Frame(root, padding=20)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题标签
        title = ttk.Label(self.main_frame, text="癫痫脑电数据分析系统", font=("Helvetica", 16, "bold"))
        title.pack(pady=10)
        
        # 用户ID输入区
        id_frame = ttk.Frame(self.main_frame)
        id_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(id_frame, text="用户ID:").pack(side=tk.LEFT, padx=(0, 10))
        self.user_id = tk.StringVar()  # ID输入框变量
        id_entry = ttk.Entry(id_frame, textvariable=self.user_id, width=30)
        id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 文件选择区域
        file_frame = ttk.LabelFrame(self.main_frame, text="脑电数据文件", padding=10)
        file_frame.pack(fill=tk.X, pady=10)
        
        self.file_path = tk.StringVar()  # 文件路径变量
        file_entry = ttk.Entry(file_frame, textvariable=self.file_path)
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        # 文件浏览按钮
        browse_btn = ttk.Button(
            file_frame, 
            text="浏览...", 
            command=self.browse_file,
            style='primary.TButton'  # 主色调按钮
        )
        browse_btn.pack(side=tk.RIGHT)
        
        # 控制按钮区域
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(fill=tk.X, pady=20)
        
        # 发送数据按钮 (处理离线文件)
        self.send_btn = ttk.Button(
            btn_frame,
            text="发送数据",
            command=self.start_processing,
            style='success.TButton',  # 成功色调
            state=tk.DISABLED  # 初始禁用
        )
        self.send_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 实时监测切换按钮
        self.realtime_btn = ttk.Button(
            btn_frame,
            text="开始实时监测",
            command=self.toggle_realtime_monitor,
            style='info.TButton',  # 信息色调
            state=tk.DISABLED  # 初始禁用
        )
        self.realtime_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 清除按钮
        clear_btn = ttk.Button(
            btn_frame,
            text="清除",
            command=self.clear_fields,
            style='warning.TButton'  # 警告色调
        )
        clear_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # 退出按钮
        exit_btn = ttk.Button(
            btn_frame,
            text="退出",
            command=root.destroy,
            style='danger.TButton'  # 危险色调
        )
        exit_btn.pack(side=tk.LEFT)
        
        # 日志输出区域
        log_frame = ttk.LabelFrame(self.main_frame, text="操作日志", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 带滚动条的文本区域
        self.log_text = scrolledtext.ScrolledText(
            log_frame, 
            height=15, 
            wrap=tk.WORD,  # 按单词换行
            font=("Consolas", 10)  # 等宽字体
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 重定向标准输出/错误到日志框
        sys.stdout = TextRedirector(self.log_text, "stdout")
        sys.stderr = TextRedirector(self.log_text, "stderr")
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 实时监测器实例 (延迟初始化)
        self.realtime_monitor = None
        
        # 输入字段变化监听
        self.user_id.trace_add("write", self.check_fields)
        self.file_path.trace_add("write", self.check_fields)
    
    def browse_file(self):
        """打开文件选择对话框"""
        filetypes = [("HDF5文件", "*.h5"), ("所有文件", "*.*")]
        file_path = filedialog.askopenfilename(title="选择脑电数据文件", filetypes=filetypes)
        if file_path:
            self.file_path.set(file_path)
            print(f"已选择文件: {file_path}")
    
    def check_fields(self, *args):
        """
        检查输入字段状态并更新按钮
        规则:
        - 发送按钮: 需要用户ID和文件路径
        - 实时监测按钮: 仅需用户ID
        """
        user_id_valid = bool(self.user_id.get())
        file_path_valid = bool(self.file_path.get())
        
        # 更新按钮状态
        self.send_btn.config(state=tk.NORMAL if user_id_valid and file_path_valid else tk.DISABLED)
        self.realtime_btn.config(state=tk.NORMAL if user_id_valid else tk.DISABLED)
    
    def clear_fields(self):
        """重置所有输入字段和状态"""
        self.user_id.set("")
        self.file_path.set("")
        self.log_text.delete(1.0, tk.END)  # 清空日志
        self.status_var.set("就绪")  # 重置状态
        print("已清除所有字段")
        
        # 停止运行中的实时监测
        if self.realtime_monitor and self.realtime_monitor.running:
            self.realtime_monitor.stop()
            self.realtime_btn.config(text="开始实时监测")
    
    def toggle_realtime_monitor(self):
        """切换实时监测状态"""
        user_id = self.user_id.get().strip()
        if not user_id:
            messagebox.showerror("错误", "请输入用户ID")
            return
            
        if self.realtime_monitor and self.realtime_monitor.running:
            # 停止实时监测
            self.realtime_monitor.stop()
            self.realtime_btn.config(text="开始实时监测")
        else:
            # 启动实时监测
            if self.realtime_monitor:
                self.realtime_monitor.stop()  # 确保停止现有实例
                
            # 创建新的监测器实例
            self.realtime_monitor = RealTimeMonitor(
                user_id,
                log_callback=self.log_message,
                status_callback=self.update_status
            )
            self.realtime_monitor.start()
            self.realtime_btn.config(text="停止实时监测")
    
    def log_message(self, message):
        """日志消息处理 (附加到日志框并滚动到底部)"""
        self.log_text.configure(state="normal")  # 临时启用编辑
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)  # 滚动到末尾
        self.log_text.configure(state="disabled")  # 禁用编辑
        self.log_text.update()  # 立即刷新
        
    def update_status(self, status):
        """更新状态栏文本"""
        self.status_var.set(status)
    
    def start_processing(self):
        """启动离线数据处理线程"""
        user_id = self.user_id.get()
        path = self.file_path.get()
        
        # 文件存在性检查
        if not os.path.exists(path):
            messagebox.showerror("错误", f"文件不存在: {path}")
            return
        
        # 禁用按钮防止重复点击
        self.send_btn.config(state=tk.DISABLED)
        self.status_var.set("处理中...")
        
        # 在新线程中处理数据 (避免阻塞GUI)
        threading.Thread(
            target=self.process_data, 
            args=(path, user_id),
            daemon=True  # 守护线程随主进程退出
        ).start()
    
    def process_data(self, path, user_id):
        """离线数据处理主流程"""
        try:
            print(f"开始处理用户 {user_id} 的数据文件: {os.path.basename(path)}")
            
            # 步骤1: 生成并上传波形图
            self.generate_and_upload_waveform(path, user_id)
            
            # 步骤2: 传输原始数据文件
            if not self.send_data(path, user_id):
                self.status_var.set("文件传输失败")
                return
            
            print("数据处理完成!")
            self.status_var.set("处理完成")
            
        except Exception as e:
            print(f"处理错误: {str(e)}")
            self.status_var.set(f"错误: {str(e)}")
        finally:
            # 重新启用发送按钮 (在GUI线程执行)
            self.root.after(100, lambda: self.send_btn.config(state=tk.NORMAL))
    
    def create_eeg_plot(self, path):
        """
        创建多通道脑电图
        :param path: HDF5文件路径
        :return: matplotlib figure对象
        """
        plt.clf()  # 清除当前图形
        # 读取HDF5数据集
        with h5py.File(path, 'r') as f:
            data = np.array(f['data'][:])  # 数据形状: (通道数, 样本数)
        
        # 创建多子图布局 (每通道一行)
        plt.figure(figsize=(12, 3*data.shape[0]))
        for ch in range(data.shape[0]):
            plt.subplot(data.shape[0], 1, ch+1)
            plt.plot(data[ch], linewidth=0.5)
            plt.ylabel(f'Ch{ch+1}', rotation=0, labelpad=20)
            plt.ylim(-500, 500)  # 固定Y轴范围
        return plt
    
    def plot_to_base64(self, plt):
        """转换matplotlib图形为base64字符串"""
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=100)
        plt.close()  # 关闭图形释放内存
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode('utf-8')
    
    def generate_and_upload_waveform(self, path, user_id):
        """离线波形图生成与上传流程"""
        # 生成脑电波形图
        fig = self.create_eeg_plot(path)
        fig.savefig('waveform_plot.png', dpi=100, bbox_inches='tight')  # 本地保存(可选)
        img_base64 = self.plot_to_base64(fig)
        
        # 构建上传负载
        payload = {
            "user_id": user_id,
            "waveform_data": img_base64,
            "api_key": API_KEY  # 简单密钥验证
        }
        
        # 生成API签名
        timestamp = str(int(time.time()))
        nonce = str(random.randint(100000, 999999))
        params = [API_KEY, timestamp, nonce]
        params.sort()
        raw_string = ''.join(params)
        signature = hashlib.sha1(raw_string.encode('utf-8')).hexdigest()
        
        # 设置请求头
        headers = {
            'Content-Type': 'application/json',
            'Signature': signature,
            'Timestamp': timestamp,
            'Nonce': nonce
        }
        
        # 发送上传请求
        try:
            print("上传脑电波形图...")
            response = requests.post(
                f"{SERVER_URL}/api/upload-waveform",
                json=payload,
                headers=headers,
                timeout=20  # 长超时时间
            )
            
            if response.status_code == 200:
                print(f"上传成功! 服务器时间: {response.json().get('timestamp')}")
            else:
                print(f"上传失败: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"上传异常: {str(e)}")
    
    def send_data(self, path, user_id):
        """
        使用TCP套接字传输数据文件
        :return: 成功返回True, 失败返回False
        """
        host = '192.168.137.100'  # 目标主机IP
        port = 5000  # 目标端口
        
        try:
            print(f"向 {host}:{port} 传输文件...")
            
            # 读取文件二进制内容
            with open(path, 'rb') as f:
                file_data = f.read()
            
            # 构建元数据头 (纯文本协议)
            header = f"USER_ID:{user_id}\nFILE_SIZE:{len(file_data)}\n\n"
            header_bytes = header.encode('utf-8')
            
            # 创建TCP连接
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10)  # 10秒超时
                s.connect((host, port))
                
                # 先发送元数据头
                s.sendall(header_bytes)
                # 再发送文件数据
                s.sendall(file_data)
            
            # 传输成功日志
            file_size = os.path.getsize(path)
            print(f"传输成功! 用户: {user_id}, 大小: {file_size} bytes")
            return True
            
        except socket.timeout:
            print("错误: 连接超时")
            return False
        except ConnectionRefusedError:
            print("错误: 连接被拒绝")
            return False
        except Exception as e:
            print(f"传输失败: {str(e)}")
            return False

# ===================== 日志重定向器 =====================
class TextRedirector(object):
    """重定向标准输出/错误到ScrolledText组件"""
    
    def __init__(self, widget, tag="stdout"):
        """
        :param widget: ScrolledText组件实例
        :param tag: 文本标签 (stdout/stderr)
        """
        self.widget = widget
        self.tag = tag
    
    def write(self, str):
        """写入文本并应用样式标签"""
        self.widget.configure(state="normal")  # 临时启用编辑
        self.widget.insert(tk.END, str, (self.tag,))  # 插入带标签文本
        self.widget.see(tk.END)  # 强制滚动到底部
        self.widget.configure(state="disabled")  # 恢复禁用状态
        self.widget.update()  # 立即刷新GUI显示
    
    def flush(self):
        """兼容文件接口的空方法"""
        pass

# ===================== 主程序入口 =====================
if __name__ == "__main__":
    root = tk.Tk()
    app = EpilepsyApp(root)
    
    # 配置日志标签样式
    app.log_text.tag_config("stdout", foreground="blue")  # 标准输出为蓝色
    app.log_text.tag_config("stderr", foreground="red")   # 标准错误为红色
    
    root.mainloop()  # 启动GUI事件循环