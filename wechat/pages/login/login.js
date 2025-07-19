const request = require('../../utils/request.js');
const BASE_URL = 'https://epilepsy.host/api';

Page({
  data: {
    username: '',
    password: '',
    isLoading: false,
    errorMessage: ''
  },

  onUsernameInput(e) {
    this.setData({ username: e.detail.value });
  },

  onPasswordInput(e) {
    this.setData({ password: e.detail.value });
  },
  onLogin() {
    // ...验证代码...
    const { username, password } = this.data;
    
    if (!username || !password) {
      this.setData({ errorMessage: '请输入用户名和密码' });
      return;
    }
    
    this.setData({ isLoading: true, errorMessage: '' });
    // 使用 request.post 方法
    request.post('/login', {
      username: this.data.username,
      password: this.data.password
    }, (res) => {
      this.setData({ isLoading: false });
      
      if (res.data && res.data.success) {
        // 保存用户ID到全局数据和本地存储
        const app = getApp();
        app.globalData.userId = res.data.user_id;
        wx.setStorageSync('userId', res.data.user_id);
        
        // 跳转到个人中心
        wx.switchTab({
          url: '/pages/person/person'
        });
      } else {
        this.setData({ errorMessage: res.data.message || '登录失败' });
      }
    }, (err) => {
      this.setData({ 
        isLoading: false,
        errorMessage: '网络错误，请重试'
      });
    });
  },
  /*onLogin() {
    const { username, password } = this.data;
    
    if (!username || !password) {
      this.setData({ errorMessage: '请输入用户名和密码' });
      return;
    }
    
    this.setData({ isLoading: true, errorMessage: '' });
    
    request.post(`${BASE_URL}/login`, {
      username,
      password
    }, (res) => {
      this.setData({ isLoading: false });
      
      if (res.data.success) {
        // 保存用户凭证
        wx.setStorageSync('token', res.data.token);
        wx.setStorageSync('userId', res.data.user_id);
        
        // 设置全局数据
        const app = getApp();
        app.globalData.token = res.data.token;
        app.globalData.userId = res.data.user_id;
        
        // 跳转到癫痫检测页面
        wx.switchTab({
          url: '/pages/eeg/eeg'
        });
      } else {
        this.setData({ errorMessage: res.data.message || '登录失败，请检查用户名和密码' });
      }
    }, (err) => {
      this.setData({ 
        isLoading: false,
        errorMessage: '网络错误，请重试'
      });
    });
  },*/

  onRegister() {
    wx.navigateTo({
      url: '/pages/register/register'
    });
  }
});