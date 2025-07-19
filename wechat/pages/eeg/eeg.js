
/*const request = require('../../utils/request.js');
const BASE_URL = 'https://epilepsy.host';
Page({
  data: {
    isDetecting: false,
    currentIndex: 0,
    plot_type: 'time_domain',//time_domain时域，spectrum频域
    result: "等待检测启动",
    probability: 0,
    resultFontSize: '32rpx',
    resultColor: '#333',
    statusText: "未启动",
    waveformImage: null, //改为url*******************
    channelCount: 0,
    imageHeight: 0,
    //currentStatus: -1 // 状态追踪变量
  },

  timer: null,
  audioContext: null, // 延迟初始化

    // 在 onLoad 函数开头添加
    onLoad() {
        const app = getApp();
        if (!app.globalData.userId) {
        wx.reLaunch({
            url: '/pages/login/login'
        });
        return;
        }
    
    // 初始化音频系统
    this.initAudioSystem();
  },

  initAudioSystem() {
    // 创建音频上下文
    this.audioContext = {
      preAudio: wx.createInnerAudioContext(),
      criticalAudio: wx.createInnerAudioContext()
    };
  
    // 使用服务器上的音频文件
    [this.audioContext.preAudio, this.audioContext.criticalAudio].forEach(audio => {
      audio.autoplay = false;
      audio.obeyMuteSwitch = false;
      audio.onError(this.handleAudioError.bind(this));
      
      // 服务器上的音频文件路径
      const filename = audio === this.audioContext.preAudio ? 'warning.mp3' : 'alarm.mp3';
      audio.src = `${BASE_URL}/audio/${filename}`;
    });
  },

  // 统一停止音频方法
  stopAllAudio() {
    this.audioContext.preAudio.stop();
    this.audioContext.criticalAudio.stop();
  },

  handleAudioError(err) {
    console.error('音频错误:', err);
    wx.showToast({ title: '警报系统异常', icon: 'none' });
  },

  onUnload() {
    this.stopDetection();
    this.audioContext.preAudio.destroy();
    this.audioContext.criticalAudio.destroy();
  },

  onHide() {
    this.stopDetection();
    this.audioContext.preAudio.stop();
    this.audioContext.criticalAudio.stop();
  },

  toggleDetection() {
    if (this.data.isDetecting) {
      this.stopDetection();
    } else {
      this.startDetection();
    }
  },

  startDetection() {
    wx.showLoading({
      title: '初始化中...',
    });

    this.setData({ 
      isDetecting: true,
      currentIndex: 0,
      statusText: "检测中...",
      result: "数据采集中...",
      probability: 0,
      waveformImage: null,
      //currentStatus: -1
    }, () => {
      wx.hideLoading();
      this.sendRequest();
    });
  },

  stopDetection() {
    clearTimeout(this.timer);
    this.timer = null;
    this.stopAllAudio();
    
    this.setData({
      isDetecting: false,
      statusText: "已停止",
      result: "检测已停止",
      probability: 0,
      //waveformImage: null
    });
    
    request.post('/reset', {}, () => {});
  },

  sendRequest() {
    if (!this.data.isDetecting) return;

    request.post('/predict', { 
      index: this.data.currentIndex,
      plot_type: this.data.plot_type 
    }, (res) => {
      if (res.data.status === 'error') {
        wx.showToast({
          title: '检测完成',
          icon: 'none'
        });
        this.stopDetection();
        return;
      }
      const prediction = res.data.prediction;
      const predictionMap = {
        0: '发作间期（正常）',
        1: '发作前期 ⚠️',
        2: '发作期 🚨',
        3: '发作后期'
      };

      this.stopAllAudio();// 处理新数据前停止所有音频
      if (prediction === 1) {
        this.audioContext.preAudio.play();
      } else if (prediction === 2) {
        this.audioContext.criticalAudio.play();
      }

      this.updateDisplay(
        predictionMap[res.data.prediction],
        res.data.probability * 100,
        res.data.image_url
      );
      
      this.setData({ 
        currentIndex: res.data.next_index 
      });

      this.timer = setTimeout(() => {
        this.sendRequest();
      }, 4000);
    });
  },

  updateDisplay(result, probability, waveform) {
    let fontSize = '32rpx';
    let color = '#333';
    
    if (result.includes('发作前期')) {
      color = '#FFC107';
      fontSize = '36rpx';
    } else if (result.includes('发作期')) {
      color = '#FF4444';
      fontSize = '40rpx';
    }

    // 获取图像尺寸信息
    if (waveform) {
        const windowInfo = wx.getWindowInfo();
        const imageWidth = windowInfo.windowWidth * 0.9;
        const channels = this.data.channelCount || 18; // 根据实际通道数调整
        const imageHeight = imageWidth * (channels * 0.3); // 动态计算高度
        
        this.setData({
          channelCount: channels,
          imageHeight: imageHeight
        })
    }
    const waveformImage = waveformPath ? `${BASE_URL}/waveforms/${waveformPath}` : null;
    this.setData({
      result,
      probability: probability.toFixed(2),
      resultColor: color,
      resultFontSize: fontSize,
      waveformImage
    });
  },
});*/

/*const request = require('../../utils/request.js');
const app = getApp();

Page({
  data: {
    waveformImage: null,
    isLoading: false,
    isMonitoring: false,
    statusText: "就绪",
    result: "点击开始检测按钮",
    createdTime: "",
    timer: null,
    imageHeight: 800
  },

  onLoad() {
    if (!app.globalData.userId) {
      wx.reLaunch({ url: '/pages/login/login' });
    }
  },
  
  onUnload() {
    this.stopMonitoring();
  },

  toggleMonitoring() {
    if (this.data.isMonitoring) {
      this.stopMonitoring();
    } else {
      this.startMonitoring();
    }
  },
  
  startMonitoring() {
    this.setData({
      isMonitoring: true,
      isLoading: true,
      statusText: "检测中...",
      result: "正在获取实时脑电波形"
    });
    
    // 立即获取一次
    this.fetchWaveform();
    
    // 设置HTTP轮询定时器（200ms间隔）
    const timer = setInterval(() => {
      this.fetchWaveform();
    }, 200);
    
    this.setData({ timer });
  },
  
  stopMonitoring() {
    if (this.data.timer) {
      clearInterval(this.data.timer);
    }
    
    // 清理服务器数据
    this.cleanServerData();
    
    this.setData({
      isMonitoring: false,
      isLoading: false,
      statusText: "已停止",
      result: "检测已停止",
      timer: null
    });
  },
  
  fetchWaveform() {
    const userId = app.globalData.userId;
    
    request.get('/api/get-latest-waveform', {
      user_id: userId
    }, (res) => {
      if (res.data && res.data.success) {
        const base64Data = `data:image/png;base64,${res.data.waveform_data}`;
        const windowInfo = wx.getWindowInfo();
        const imageHeight = windowInfo.windowWidth * 1.5;  // 动态计算高度
        
        this.setData({
          waveformImage: base64Data,
          createdTime: res.data.created_at,
          statusText: "实时监测中",
          result: "最新脑电波形图",
          isLoading: false,
          imageHeight: imageHeight
        });
      } else {
        this.setData({
          statusText: "获取失败",
          result: res.data?.message || '获取波形图失败',
          isLoading: false
        });
      }
    }, (err) => {
      this.setData({
        isLoading: false,
        statusText: "请求失败",
        result: '网络错误，请重试'
      });
    });
  },
  
  cleanServerData() {
    const userId = app.globalData.userId;
    
    request.post('/clean-waveform', {
      user_id: userId
    }, (res) => {
      if (res.data && res.data.success) {
        console.log("服务器数据清理成功");
      } else {
        console.error("数据清理失败:", res.data?.message);
      }
    }, (err) => {
      console.error("清理请求失败:", err);
    });
  }
});*/

const request = require('../../utils/request.js');
const app = getApp();
const BASE_URL = 'https://epilepsy.host';

Page({
  data: {
    isDetecting: false,       // 检测状态
    statusText: "未启动",     // 状态文本
    result: "等待检测启动",   // 检测结果
    resultFontSize: '32rpx',  // 结果字体大小
    resultColor: '#333',      // 结果文本颜色
    waveformImage: null,      // 波形图URL
    imageHeight: 800,         // 图片高度
    lastUpdateTime: "",        // 最后更新时间
    timer: null               // 轮询定时器
  },

  onLoad() {
    if (!app.globalData.userId) {
      wx.reLaunch({ url: '/pages/login/login' });
    }
  },
  
  onUnload() {
    this.stopDetection();
  },

  // 切换检测状态
  toggleDetection() {
    if (this.data.isDetecting) {
      this.stopDetection();
    } else {
      this.startDetection();
    }
  },
  
  // 开始检测
  startDetection() {
    this.setData({
      isDetecting: true,
      statusText: "检测中...",
      result: "数据采集中..."
    });
    
    // 立即获取一次数据
    this.fetchWaveform();
    
    // 设置定时器（每1500ms请求一次）
    const timer = setInterval(() => {
      this.fetchWaveform();
    }, 1500);
    
    this.setData({ timer });
  },
  
  // 停止检测（已移除清理服务器数据功能）
  stopDetection() {
    if (this.data.timer) {
      clearInterval(this.data.timer);
    }
    
    // 仅更新本地状态，不再向服务器发送清理请求
    this.setData({
      isDetecting: false,
      statusText: "已停止",
      result: "检测已停止",
      timer: null
    });
  },
  
  // 获取波形图数据
  fetchWaveform() {
    const userId = app.globalData.userId;
    
    request.get('/api/get-latest-waveform', {
      user_id: userId
    }, (res) => {
      if (res.data && res.data.success) {
        const base64Data = `data:image/png;base64,${res.data.waveform_data}`;
        const windowInfo = wx.getWindowInfo();
        const imageHeight = windowInfo.windowWidth * 1.2;  // 动态计算高度
        
        // 解析预测结果
        let result = "脑电信号正常";
        let fontSize = '32rpx';
        let color = '#333';
        
        this.setData({
          waveformImage: base64Data,
          lastUpdateTime: res.data.created_at,
          statusText: "实时监测中",
          result,
          resultColor: color,
          resultFontSize: fontSize,
          imageHeight
        });
      } else {
        this.setData({
          statusText: "获取失败",
          result: res.data?.message || '获取波形图失败'
        });
      }
    }, (err) => {
      this.setData({
        statusText: "请求失败",
        result: '网络错误，请重试'
      });
    });
  }
});