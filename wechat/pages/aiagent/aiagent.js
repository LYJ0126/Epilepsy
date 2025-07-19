// pages/aiagent/aiagent.js
// pages/aiagent/aiagent.js
const app = getApp();

Page({
  data: {
    question: '',
    answer: '',
    loading: false,
    chatHistory: [],
    structuredAnswer: null,
    requestId: null,
    processingTime: 0,
    showTimeoutWarning: false,
    refreshing: false,
    scrollTop: 0,
    navbarHeight: 0
  },

  onLoad() {
    // 计算导航栏高度
    const systemInfo = wx.getSystemInfoSync();
    const navbarHeight = systemInfo.statusBarHeight + (systemInfo.platform === 'android' ? 48 : 44);
    this.setData({ navbarHeight });
    
    // 加载历史记录
    const history = wx.getStorageSync('chatHistory') || [];
    this.setData({ chatHistory: history });
  },

  onInputQuestion(e) {
    this.setData({ question: e.detail.value });
  },

  onRefresh() {
    this.setData({ refreshing: true });
    // 模拟刷新
    setTimeout(() => {
      this.setData({ refreshing: false });
      wx.showToast({ title: '已刷新', icon: 'success' });
    }, 1000);
  },

  async askQuestion() {
    if (!this.data.question.trim()) return;
    
    // 重置状态
    this.setData({
      loading: true,
      showTimeoutWarning: false,
      processingTime: 0
    });
    
    // 添加到聊天历史
    const newHistory = [...this.data.chatHistory, 
      { 
        role: 'user', 
        content: this.data.question,
        timestamp: this.getCurrentTime()
      }
    ];
    this.setData({ chatHistory: newHistory });
    
    // 滚动到底部
    this.scrollToBottom();
    
    try {
      // 生成请求ID用于追踪
      const requestId = Date.now().toString();
      this.setData({ requestId });
      
      // 启动计时器
      const startTime = Date.now();
      const timer = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        this.setData({ processingTime: elapsed });
        
        // 5秒后显示超时提示
        if (elapsed >= 5 && !this.data.showTimeoutWarning) {
          this.setData({ showTimeoutWarning: true });
        }
      }, 1000);
      
      // 调用服务器 API
      const res = await new Promise((resolve, reject) => {
        wx.request({
          url: 'https://epilepsy.host/api/epilepsy-consult',
          method: 'POST',
          header: {
            'Content-Type': 'application/json',
            'X-Request-ID': requestId
          },
          data: {
            question: this.data.question
          },
          timeout: 30000,
          success: resolve,
          fail: reject
        });
      });
      
      // 清除计时器
      clearInterval(timer);
      
      // 处理响应
      if (res.statusCode !== 200) {
        throw new Error(`服务器错误: ${res.statusCode}`);
      }
      
      const answer = res.data.answer;
      const structuredAnswer = res.data.structuredAnswer;
      
      // 添加到聊天历史
      newHistory.push({ 
        role: 'assistant', 
        content: answer,
        structuredAnswer,
        timestamp: this.getCurrentTime()
      });
      
      this.setData({
        chatHistory: newHistory,
        answer: answer,
        question: '',
        loading: false,
        structuredAnswer,
        showTimeoutWarning: false,
        processingTime: 0
      });
      
      // 保存历史记录
      wx.setStorageSync('chatHistory', newHistory);
      
      // 滚动到底部
      this.scrollToBottom();
      
    } catch (err) {
      console.error('咨询失败:', err);
      
      // 清除计时器
      clearInterval(timer);
      
      // 处理超时错误
      let errorMsg = err.message || '请重试';
      if (err.errMsg && err.errMsg.includes('timeout')) {
        errorMsg = '思考时间过长，请简化问题或稍后再试';
      }
      
      wx.showToast({ 
        title: `咨询失败: ${errorMsg}`, 
        icon: 'none',
        duration: 3000
      });
      
      this.setData({ 
        loading: false,
        showTimeoutWarning: false,
        processingTime: 0
      });
    }
  },

  scrollToBottom() {
    this.setData({
      scrollTop: 99999  // 设置一个足够大的值确保滚动到底部
    });
  },
  
  getCurrentTime() {
    const now = new Date();
    return `${now.getHours()}:${now.getMinutes().toString().padStart(2, '0')}`;
  },

  callEmergency() {
    wx.makePhoneCall({ phoneNumber: '120' });
  },
  
  copyAnswer() {
    if (!this.data.answer) return;
    
    wx.setClipboardData({
      data: this.data.answer,
      success: () => {
        wx.showToast({
          title: '已复制到剪贴板',
          icon: 'success'
        });
      }
    });
  },
  
  reaskQuestion() {
    if (this.data.chatHistory.length > 0) {
      const lastQuestion = this.data.chatHistory
        .filter(msg => msg.role === 'user')
        .pop().content;
      
      this.setData({ question: lastQuestion });
      this.askQuestion();
    }
  },
  
  onShareAppMessage() {
    return {
      title: '癫痫健康助手',
      path: '/pages/aiagent/aiagent',
      imageUrl: '/images/share.jpg'
    };
  }
});

/*Page({
    data: {
      question: '',
      answer: '',
      loading: false,
      chatHistory: [],
      structuredAnswer: null,
      requestId: null, // 添加请求ID用于追踪
      processingTime: 0, // 处理时间（秒）
      showTimeoutWarning: false // 是否显示超时提示
    },
  
    onInputQuestion(e) {
      this.setData({ question: e.detail.value });
    },
  
    async askQuestion() {
      if (!this.data.question.trim()) return;
      
      // 重置状态
      this.setData({
        loading: true,
        showTimeoutWarning: false,
        processingTime: 0
      });
      
      // 添加到聊天历史
      const newHistory = [...this.data.chatHistory, 
        { role: 'user', content: this.data.question }
      ];
      this.setData({ chatHistory: newHistory });
      
      try {
        // 生成请求ID用于追踪
        const requestId = Date.now().toString();
        this.setData({ requestId });
        
        // 启动计时器
        const startTime = Date.now();
        const timer = setInterval(() => {
          const elapsed = Math.floor((Date.now() - startTime) / 1000);
          this.setData({ processingTime: elapsed });
          
          // 5秒后显示超时提示
          if (elapsed >= 5 && !this.data.showTimeoutWarning) {
            this.setData({ showTimeoutWarning: true });
          }
        }, 1000);
        
        // 调用服务器 API（增加超时时间）
        const res = await new Promise((resolve, reject) => {
          wx.request({
            url: 'https://epilepsy.host/api/epilepsy-consult',
            method: 'POST',
            header: {
              'Content-Type': 'application/json',
              'X-Request-ID': requestId // 添加请求ID头
            },
            data: {
              question: this.data.question
            },
            timeout: 30000, // 30秒超时
            success: resolve,
            fail: reject
          });
        });
        
        // 清除计时器
        clearInterval(timer);
        
        // 处理响应
        if (res.statusCode !== 200) {
          throw new Error(`服务器错误: ${res.statusCode}`);
        }
        
        const answer = res.data.answer;
        const structuredAnswer = res.data.structuredAnswer;
        
        // 添加到聊天历史
        newHistory.push({ 
          role: 'assistant', 
          content: answer,
          structuredAnswer
        });
        
        this.setData({
          chatHistory: newHistory,
          answer: answer,
          question: '',
          loading: false,
          structuredAnswer,
          showTimeoutWarning: false,
          processingTime: 0
        });
        
      } catch (err) {
        console.error('咨询失败:', err);
        
        // 清除计时器
        clearInterval(timer);
        
        // 处理超时错误
        let errorMsg = err.message || '请重试';
        if (err.errMsg && err.errMsg.includes('timeout')) {
          errorMsg = '思考时间过长，请简化问题或稍后再试';
        }
        
        wx.showToast({ 
          title: `咨询失败: ${errorMsg}`, 
          icon: 'none',
          duration: 3000
        });
        
        // 显示请求ID（如果有）
        if (this.data.requestId) {
          wx.showToast({
            title: `请求ID: ${this.data.requestId}`,
            icon: 'none',
            duration: 3000
          });
        }
        
        this.setData({ 
          loading: false,
          showTimeoutWarning: false,
          processingTime: 0
        });
      }
    },
  
    // 紧急求助功能
    callEmergency() {
      wx.makePhoneCall({ phoneNumber: '120' });
    },
    
    // 复制答案到剪贴板
    copyAnswer() {
      wx.setClipboardData({
        data: this.data.answer,
        success: () => {
          wx.showToast({
            title: '已复制到剪贴板',
            icon: 'success'
          });
        }
      });
    },
    
    // 重新提问
    reaskQuestion() {
      if (this.data.chatHistory.length > 0) {
        const lastQuestion = this.data.chatHistory
          .filter(msg => msg.role === 'user')
          .pop().content;
        
        this.setData({ question: lastQuestion });
        this.askQuestion();
      }
    }
  });*/
