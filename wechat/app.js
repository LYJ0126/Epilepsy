App({
    onLaunch() {
      // 尝试从本地存储加载用户ID
      const userId = wx.getStorageSync('userId');
      if (userId) {
        this.globalData.userId = userId;
      }
    },
    
    globalData: {
      userId: null,
      userInfo: null
    }
  });