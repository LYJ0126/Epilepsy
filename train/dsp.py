import numpy as np
from scipy import signal
from scipy.signal import get_window
from scipy.fftpack import fft

def pre_stft(data_signal, sample_rate, win_len, overlap_len, cutoff_hz):
    """
    计算输入信号的短时傅里叶变换（STFT），并提取指定截止频率以下的频谱幅度。
    
    参数：
        data_signal (ndarray)：输入信号，形状为 (data_num, electro_num, length)，表示多个数据样本的多个电极通道。
        sample_rate (int)：信号的采样率（Hz）。
        win_len (int)：STFT的窗口长度（样本数）。
        overlap_len (int)：相邻窗口的重叠长度（样本数）。
        cutoff_hz (float)：截止频率（Hz），仅保留低于此频率的频谱成分。
    
    返回：
        ndarray：STFT结果，形状为 (data_num, electro_num, num, cutoff)，其中 num 是时间窗口数量。
    """
    # 获取输入信号的维度
    data_num = data_signal.shape[0]  # 数据样本数
    electro_num = data_signal.shape[1]  # 电极通道数
    length = data_signal.shape[2]  # 信号长度
    
    # 计算截止频率对应的频谱bin数
    # 频率分辨率为 sample_rate / win_len Hz/bin，截止bin数为 ceil(cutoff_hz / (sample_rate / win_len))
    cutoff = int(np.ceil(cutoff_hz * win_len / sample_rate))
    
    # 计算时间窗口数量
    num = int((length - win_len) / overlap_len + 3)  # +3 确保覆盖所有信号，可能包含部分填充
    
    # 初始化结果数组，存储每个样本、通道、时间窗口和频率bin的频谱幅度
    res = np.zeros((data_num, electro_num, num, cutoff), dtype=np.float32)
    
    # 生成Hann窗口，用于平滑信号
    window = get_window('hann', win_len)
    
    # 初始化带零填充的信号数组，左右各填充 overlap_len 个零以处理边界
    src = np.zeros((data_num, electro_num, length + 2 * overlap_len), dtype=data_signal.dtype)
    src[:, :, overlap_len:length + overlap_len] = data_signal
    
    # 对每个样本和通道进行STFT
    for i in range(data_num):
        for j in range(electro_num):
            for batch_t in range(num):
                # 提取当前时间窗口的信号并应用Hann窗口
                start = batch_t * overlap_len
                stft_window = src[i, j, start:start + win_len] * window
                # 计算FFT并取前cutoff个bin的幅度
                res[i, j, batch_t, :] = np.abs(fft(stft_window, n=win_len)[:cutoff])
    
    return res