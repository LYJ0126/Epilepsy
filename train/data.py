import os
import h5py
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.utils import shuffle
import dsp  

def load_data(data_dir, data_type='train'):
    """
    从指定目录加载EEG数据并应用预处理
    
    参数:
        data_dir (str): 数据集根目录
        data_type (str): 数据类型 ('train' 或 'test')
        
    返回:
        tuple: (预处理后的数据数组, 标签数组)
    """
    data_path = os.path.join(data_dir, data_type)
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"目录不存在: {data_path}")
    
    # 收集所有样本文件路径
    all_files = []
    all_labels = []
    
    # 遍历标签目录
    for label in os.listdir(data_path):
        label_dir = os.path.join(data_path, label)
        if not os.path.isdir(label_dir):
            continue
            
        # 收集当前标签下的所有文件
        for filename in os.listdir(label_dir):
            if filename.endswith('.h5'):
                file_path = os.path.join(label_dir, filename)
                all_files.append(file_path)
                all_labels.append(int(label))
    
    # 初始化数据存储
    data_list = []
    labels_list = []
    
    # 打印调试信息
    print(f"从 {data_type} 集找到 {len(all_files)} 个样本")
    
    # 处理每个文件
    for file_path, label in zip(all_files, all_labels):
        try:
            with h5py.File(file_path, 'r') as hf:
                # 从文件加载数据
                sample = hf['data'][:]  # 形状应为 (18, 2560)
                
                # 应用STFT变换
                sample_rate = 256
                win_len = 256
                overlap_len = 128
                cutoff_hz = 60
                sample_stft = dsp.pre_stft(
                    sample[np.newaxis, ...],  # 添加批次维度
                    sample_rate=sample_rate,
                    win_len=win_len,
                    overlap_len=overlap_len,
                    cutoff_hz=cutoff_hz
                )
                
                # 移除添加的批次维度，获取原始形状
                sample_stft = np.squeeze(sample_stft, axis=0)
                
                # 添加到列表
                data_list.append(sample_stft)
                labels_list.append(label)
                
        except Exception as e:
            print(f"处理文件 {os.path.basename(file_path)} 时出错: {e}")
    
    # 转换为数组
    x = np.array(data_list, dtype=np.float32)  # 形状: (样本数, 18, 时间帧数, 频率bin数)
    y = np.array(labels_list, dtype=np.int64)  # 形状: (样本数,)
    
    # 标准化处理 (按频率点独立标准化)
    mean = np.mean(x, axis=0, keepdims=True)  
    std = np.std(x, axis=0, keepdims=True)
    epsilon=1e-8
    x = (x - mean) / (std + epsilon)
    if data_type == 'train':
        np.save("mean.npy", mean)
        np.save("std.npy", std)
    
    print(f"成功加载 {x.shape[0]} 个样本")
    print(f"数据形状: {x.shape}")
    print(f"标签分布: {np.unique(y, return_counts=True)[1]}")
    
    return x, y

if __name__ == "__main__":
    # 示例调用
    dataset_dir = './'  # 替换为您的数据集路径
    
    # 加载训练集
    x_train, y_train = load_data(dataset_dir, data_type='train')
    
    # 加载测试集
    x_test, y_test = load_data(dataset_dir, data_type='test')
    
    print("\n数据集统计:")
    print(f"训练集: {x_train.shape[0]} 个样本")
    print(f"测试集: {x_test.shape[0]} 个样本")
    print(f"数据维度: {x_train.shape[1:]} (通道数×时间帧数×频率数)")
