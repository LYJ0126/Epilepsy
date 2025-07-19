/*
const request = require('../../utils/request.js');
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

const request = require('../../utils/request.js');
const BASE_URL = 'https://epilepsy.host';

Page({
  data: {
    waveformImage: null, // 存储Base64格式的波形图
    isLoading: false,
    statusText: "就绪",
    result: "点击按钮获取最新脑电波形图",
    createdTime: "", // 波形图生成时间
    channelCount: 18, // 默认通道数
    imageHeight: 800 // 默认图片高度
  },

  onLoad() {
    const app = getApp();
    if (!app.globalData.userId) {
      wx.reLaunch({
        url: '/pages/login/login'
      });
    }
  },

  // 获取脑电波形图
  getWaveform() {
    const app = getApp();
    const userId = app.globalData.userId;
    
    if (!userId) {
      wx.showToast({
        title: '请先登录',
        icon: 'none'
      });
      return;
    }
    
    this.setData({
      isLoading: true,
      statusText: "获取中...",
      result: "正在从服务器获取脑电波形图"
    });
    
    // 请求服务器获取波形图数据
    request.get('/api/get-waveform', {
      user_id: userId
    }, (res) => {
      this.setData({ isLoading: false });
      
      if (res.data && res.data.success) {
        // 处理Base64数据，添加前缀
        const base64Data = `data:image/png;base64,${res.data.waveform_data}`;
        
        // 计算图片高度（根据通道数）
        const channels = this.data.channelCount;
        const windowInfo = wx.getWindowInfo();
        const imageWidth = windowInfo.windowWidth * 0.9;
        const imageHeight = imageWidth * (channels * 0.3);
        
        this.setData({
          waveformImage: base64Data,
          createdTime: res.data.created_at,
          statusText: "获取成功",
          result: "最新脑电波形图已加载",
          imageHeight: imageHeight
        });
        
        wx.showToast({
          title: '获取成功',
          icon: 'success'
        });
      } else {
        this.setData({
          statusText: "获取失败",
          result: res.data.message || '获取波形图失败'
        });
        wx.showToast({
          title: '获取失败',
          icon: 'none'
        });
      }
    }, (err) => {
      this.setData({
        isLoading: false,
        statusText: "请求失败",
        result: '网络错误，请重试'
      });
      wx.showToast({
        title: '网络错误',
        icon: 'none'
      });
    });
  },
});