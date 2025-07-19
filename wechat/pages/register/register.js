const request = require('../../utils/request.js');
const BASE_URL = 'https://epilepsy.host/api';

Page({
  data: {
    username: '',
    password: '',
    confirmPassword: '',
    isLoading: false,
    errorMessage: ''
  },

  onUsernameInput(e) {
    this.setData({ username: e.detail.value });
  },

  onPasswordInput(e) {
    this.setData({ password: e.detail.value });
  },

  onConfirmPasswordInput(e) {
    this.setData({ confirmPassword: e.detail.value });
  },

  onRegister() {
    const { username, password, confirmPassword } = this.data;
    
    if (!username || !password || !confirmPassword) {
      this.setData({ errorMessage: '请填写所有字段' });
      return;
    }
    
    if (password !== confirmPassword) {
      this.setData({ errorMessage: '两次输入的密码不一致' });
      return;
    }
    
    if (password.length < 6) {
      this.setData({ errorMessage: '密码长度至少为6位' });
      return;
    }
    
    this.setData({ isLoading: true, errorMessage: '' });
    
    request.post('/register', {
        username: this.data.username,
        password: this.data.password
      }, (res) => {
        this.setData({ isLoading: false });
        
        if (res.data && res.data.success) {
          wx.showToast({
            title: '注册成功',
            icon: 'success',
            duration: 1500,
            complete: () => {
              setTimeout(() => {
                wx.navigateBack();
              }, 1500);
            }
          });
        } else {
          this.setData({ errorMessage: res.data.message || '注册失败，请重试' });
        }
      }, (err) => {
        this.setData({ 
          isLoading: false,
          errorMessage: '网络错误，请重试'
        });
      });
  },

  onLogin() {
    wx.navigateBack();
  }
});