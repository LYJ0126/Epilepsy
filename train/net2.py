import torch
import torch.nn as nn
import torch.nn.functional as F

class h_sigmoid(nn.Module):
    def __init__(self, inplace=True):
        super(h_sigmoid, self).__init__()
        self.relu = nn.ReLU6(inplace=inplace)

    def forward(self, x):
        return self.relu(x + 3) / 6

class h_swish(nn.Module):
    def __init__(self, inplace=True):
        super(h_swish, self).__init__()
        self.sigmoid = h_sigmoid(inplace=inplace)

    def forward(self, x):
        return x * self.sigmoid(x)

class CoordAtt(nn.Module):
    def __init__(self, inp, oup, reduction=32):
        super(CoordAtt, self).__init__()
        self.pool_h = nn.AdaptiveAvgPool2d((None, 1))
        self.pool_w = nn.AdaptiveAvgPool2d((1, None))

        mip = max(8, inp // reduction)

        self.conv1 = nn.Conv2d(inp, mip, kernel_size=1, stride=1, padding=0)
        self.bn1 = nn.BatchNorm2d(mip)
        self.act = h_swish()
        
        self.conv_h = nn.Conv2d(mip, oup, kernel_size=1, stride=1, padding=0)
        self.conv_w = nn.Conv2d(mip, oup, kernel_size=1, stride=1, padding=0)
        
    def forward(self, x):
        identity = x
        
        n, c, h, w = x.size()
        x_h = self.pool_h(x)
        x_w = self.pool_w(x).permute(0, 1, 3, 2)

        y = torch.cat([x_h, x_w], dim=2)
        y = self.conv1(y)
        y = self.bn1(y)
        y = self.act(y) 
        
        x_h, x_w = torch.split(y, [h, w], dim=2)
        x_w = x_w.permute(0, 1, 3, 2)

        a_h = self.conv_h(x_h).sigmoid()
        a_w = self.conv_w(x_w).sigmoid()

        out = identity * a_w * a_h

        return out

class SimplifiedTemporalBlock(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size):
        super().__init__()
        padding = (kernel_size - 1) // 2
        
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, in_channels, (kernel_size, 1), 
                      padding=(padding, 0), 
                      groups=in_channels),
            nn.BatchNorm2d(in_channels),
            nn.ReLU(),
            nn.Conv2d(in_channels, out_channels, 1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU()
        )
        self.downsample = nn.Conv2d(in_channels, out_channels, 1) if in_channels != out_channels else nn.Identity()

    def forward(self, x):
        residual = self.downsample(x)
        x = self.conv(x)
        return F.relu(x + residual)

class EnhancedEpilepsyDetector(nn.Module):
    def __init__(self, num_electrodes=18, time_frames=21, freq_bins=60, num_classes=4):
        super().__init__()
        
        # 输入特征提取
        self.init_conv = nn.Sequential(
            nn.Conv2d(num_electrodes, 32, (3, 3), padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.Dropout(0.3)
        )
        
        # 保留CoordAtt注意力模块
        self.coordatt = CoordAtt(32, 32)
        
        # 简化时序特征提取
        self.temporal_block = SimplifiedTemporalBlock(32, 64, kernel_size=3)
        
        # 简化频率特征提取
        self.freq_branch = nn.Sequential(
            nn.Conv2d(32, 64, (1, 3), stride=(1, 2), padding=(0, 1)),
            nn.BatchNorm2d(64),
            nn.ReLU()
        )
        
        # 特征融合与分类
        self.classifier = nn.Sequential(
            nn.Linear(64 + 64, 128),  # 时序特征64 + 频率特征64
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(128, num_classes)
        )

    def forward(self, x):
        # 输入: [B, 18, 21, 60]
        x = self.init_conv(x)  # [B, 32, 21, 60]
        x = self.coordatt(x)  # 应用坐标注意力
        
        # 时序处理
        temporal_feat = self.temporal_block(x)  # [B, 64, 21, 60]
        temporal_feat = torch.mean(temporal_feat, dim=(2, 3))  # [B, 64]
        
        # 频率处理
        freq_feat = self.freq_branch(x)  # [B, 64, 21, 30]
        freq_feat = torch.mean(freq_feat, dim=(2, 3))  # [B, 64]
        
        # 特征融合
        combined = torch.cat([temporal_feat, freq_feat], dim=1)  # [B, 128]
        
        return self.classifier(combined)