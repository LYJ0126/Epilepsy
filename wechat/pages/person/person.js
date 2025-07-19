const request = require('../../utils/request.js');
const BASE_URL = 'https://epilepsy.host/api';

Page({
  data: {
    userInfo: {
      name: '',
      gender: '男',
      age: 0,
      height: 0,
      weight: 0,
      bloodType: 'A',
      bmi: 0,
      bmiStatus: "正常"
    },
    lastUpdate: '未保存',
    isEditing: false,
    userId: null
  },

    // 在 onLoad 函数开头添加
    onLoad() {
        const app = getApp();
    
        // 从全局数据或本地存储获取用户ID
        const userId = app.globalData.userId || wx.getStorageSync('userId');
        
        if (!userId) {
          wx.reLaunch({
            url: '/pages/login/login'
          });
          return;
        }
        
        // 设置用户ID到页面数据
        this.setData({
          userId: userId
        });
        
        // 加载健康数据
        this.loadHealthData();
      },
  onShow() {
    if (this.data.userId) {
      this.loadHealthData();
    }
  },

  calculateBMI() {
    const { height, weight } = this.data.userInfo;
    const newBMI = height > 0 ? (weight / Math.pow(height / 100, 2)).toFixed(1) : 0
    this.setData({
      'userInfo.bmi': newBMI,
      'userInfo.bmiStatus': this.getBMIStatus(newBMI)
    });
  },

  getBMIStatus(bmi) {
    bmi = parseFloat(bmi)
    if (bmi < 18.5) return '偏瘦'
    if (bmi < 24) return '正常'
    if (bmi < 28) return '超重'
    return '肥胖'
  },

  loadHealthData() {
    // 确保有用户ID
    if (!this.data.userId) {
      console.error("无法加载健康数据：缺少用户ID");
      wx.showToast({
        title: '请先登录',
        icon: 'none'
      });
      return;
    }
    
    // 使用 request.get 方法
    request.get('/health-data', {
      user_id: this.data.userId
    }, (res) => {
      if (res.data) {
        this.setData({
          userInfo: {
            ...this.data.userInfo,
            name: res.data.name || '',
            gender: res.data.gender || '男',
            age: res.data.age || 0,
            height: res.data.height || 0,
            weight: res.data.weight || 0,
            bloodType: res.data.blood_type || 'A'
          },
          lastUpdate: res.data.last_update || '未保存'
        });
        this.calculateBMI();
      }
    }, (err) => {
      console.error("获取健康数据失败:", err);
      wx.showToast({
        title: '获取健康数据失败',
        icon: 'none'
      });
    });
  },

  saveToStorage() {
    const name = this.data.userInfo.name.trim();
    if (!name) {
      wx.showToast({ title: '姓名不能为空', icon: 'none' });
      return;
    }
    
    // 打印将要发送的数据
    console.log("保存健康数据:", {
      user_id: this.data.userId,
      health_data: {
        name: this.data.userInfo.name,
        gender: this.data.userInfo.gender,
        age: this.data.userInfo.age,
        height: this.data.userInfo.height,
        weight: this.data.userInfo.weight,
        bloodType: this.data.userInfo.bloodType
      }
    });
    
    this.calculateBMI();
    
    request.post(`/save-health-data`, {
      // 使用 data 中的 userId
      user_id: this.data.userId,
      health_data: {
        name: this.data.userInfo.name,
        gender: this.data.userInfo.gender,
        age: this.data.userInfo.age,
        height: this.data.userInfo.height,
        weight: this.data.userInfo.weight,
        bloodType: this.data.userInfo.bloodType
      }
    }, (res) => {
      if (res.data && res.data.success) {
        wx.showToast({
          title: '保存成功',
          icon: 'success'
        });
        this.setData({
          lastUpdate: res.data.last_update || '未知时间',
          isEditing: false
        });
      } else {
        console.error("保存失败:", res.data);
        wx.showToast({
          title: '保存失败，请重试',
          icon: 'none'
        });
      }
    }, (err) => {
      console.error("保存出错:", err);
      wx.showToast({
        title: '网络错误，请重试',
        icon: 'none'
      });
    });
  },

  

  toggleEdit() {
    this.setData({
      isEditing: !this.data.isEditing
    });
  },

  handlePickerChange(e) {
    const field = e.currentTarget.dataset.field
    const valueMap = {
      gender: ['男', '女'],
      bloodType: ['A', 'B', 'AB', 'O']
    }
    const selectedValue = valueMap[field][e.detail.value]
    
    this.setData({
      [`userInfo.${field}`]: selectedValue
    })
  },

  handleInputChange(e) {
    const { field } = e.currentTarget.dataset;
    const value = e.detail.value;
    this.setData({
      [`userInfo.${field}`]: field === 'age' || field === 'height' || field === 'weight' ? Number(value) : value
    });
  }
});




