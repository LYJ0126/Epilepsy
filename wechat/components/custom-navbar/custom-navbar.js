// components/custom-navbar/custom-navbar.js
Component({
    properties: {
      title: {
        type: String,
        value: '癫痫健康助手'
      },
      showBack: {
        type: Boolean,
        value: false
      },
      showEmergency: {
        type: Boolean,
        value: true
      },
      bgColor: {
        type: String,
        value: '#1890ff'
      }
    },
    
    data: {
      statusBarHeight: 0,
      navBarHeight: 44
    },
    
    lifetimes: {
      attached() {
        const systemInfo = wx.getSystemInfoSync();
        this.setData({
          statusBarHeight: systemInfo.statusBarHeight,
          navBarHeight: systemInfo.platform === 'android' ? 48 : 44
        });
      }
    },
    
    methods: {
      goBack() {
        wx.navigateBack();
      },
      
      onEmergency() {
        wx.makePhoneCall({ phoneNumber: '120' });
      },
      
      onUser() {
        wx.navigateTo({ url: '/pages/profile/profile' });
      }
    }
  });