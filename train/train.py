import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
from data import load_data
import os
from net2 import EnhancedEpilepsyDetector


def train_model(model, train_loader, val_loader, criterion, optimizer, scheduler, 
                num_epochs, device, model_save_path):
    """
    训练带学习率调度的癫痫检测模型
    
    参数:
        model: 待训练模型
        train_loader: 训练数据加载器
        val_loader: 验证数据加载器
        criterion: 损失函数
        optimizer: 优化器
        scheduler: 学习率调度器
        num_epochs: 训练周期数
        device: 训练设备 (CPU/GPU)
        model_save_path: 模型保存路径
    """
    best_val_acc = 0.0
    best_epoch = 0
    learning_rates = []  # 记录学习率变化
    
    for epoch in range(num_epochs):
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        
        # 训练阶段
        for inputs, labels in train_loader:
            inputs, labels = inputs.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * inputs.size(0)
            _, predicted = torch.max(outputs, 1)
            train_total += labels.size(0)
            train_correct += (predicted == labels).sum().item()
        
        # 计算当前学习率并记录
        current_lr = optimizer.param_groups[0]['lr']
        learning_rates.append(current_lr)
        
        # 更新学习率调度器
        scheduler.step()
        
        train_loss /= train_total
        train_acc = train_correct / train_total
        
        # 验证阶段
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                
                val_loss += loss.item() * inputs.size(0)
                _, predicted = torch.max(outputs, 1)
                val_total += labels.size(0)
                val_correct += (predicted == labels).sum().item()
        
        val_loss /= val_total
        val_acc = val_correct / val_total
        
        print(f'Epoch {epoch+1}/{num_epochs} | LR: {current_lr:.6f}')
        print(f'Train Loss: {train_loss:.4f}, Acc: {train_acc:.4f} | Val Loss: {val_loss:.4f}, Acc: {val_acc:.4f}')

        # 保存最佳模型
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch = epoch
            # 保存模型
            torch.save(model.state_dict(), model_save_path)
            print(f'✓ 模型保存至 {model_save_path}, 验证准确率: {val_acc:.4f}')
    
    print(f'训练完成 | 最佳验证准确率: {best_val_acc:.4f} (epoch {best_epoch+1})')
    return learning_rates

def main():
    data_dir = './'
    model_dir = 'saved_models'
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
    
    model_save_path = os.path.join(model_dir, 'epilepsy_cnn_best_model.pth')
    
    # 加载数据
    x_train, y_train = load_data(data_dir, data_type='train')
    x_val, y_val = load_data(data_dir, data_type='test')
    
    num_electrodes = x_train.shape[1]
    time_frames = x_train.shape[2]
    freq_bins = x_train.shape[3]
    
    # 转换为PyTorch张量
    x_train = torch.from_numpy(x_train).float()
    y_train = torch.from_numpy(y_train).long()
    x_val = torch.from_numpy(x_val).float()
    y_val = torch.from_numpy(y_val).long()
    
    # 创建数据集和数据加载器
    train_dataset = TensorDataset(x_train, y_train)
    val_dataset = TensorDataset(x_val, y_val)
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32)
    
    # 设置训练设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = EnhancedEpilepsyDetector(num_electrodes, time_frames, freq_bins).to(device)
    
    # 损失函数和优化器
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    
    # 余弦退火学习率调度器（周期为50）
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=50)
    
    # 启动训练（传递scheduler参数）
    learning_rates = train_model(
        model, train_loader, val_loader, criterion, 
        optimizer, scheduler, num_epochs=30, 
        device=device, model_save_path=model_save_path
    )

if __name__ == "__main__":
    main()
