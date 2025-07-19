const baseUrl = 'https://epilepsy.host/api'; 

// GET 请求方法
//function get(url, data, success, fail) {
//  wx.request({
//    url: baseUrl + url,
//    method: 'GET',
//    data: data,
//    success: (res) => {
//      if (res.statusCode >= 200 && res.statusCode < 300) {
//        success && success(res);
//      } else {
//        fail && fail({
//          statusCode: res.statusCode,
//          data: res.data
//        });
//      }
//    },
//    fail: (err) => {
//      fail && fail(err);
//    }
//  });
//}

// GET 请求方法
function get(url, data, success, fail) {
  // 将data对象转换为查询字符串
  let query = '';
  if (data) {
    query = '?' + Object.keys(data).map(key => 
      `${encodeURIComponent(key)}=${encodeURIComponent(data[key])}`
    ).join('&');
  }
  
  wx.request({
    url: baseUrl + url + query,
    method: 'GET',
    success: (res) => {
      if (res.statusCode >= 200 && res.statusCode < 300) {
        success && success(res);
      } else {
        fail && fail({
          statusCode: res.statusCode,
          data: res.data
        });
      }
    },
    fail: (err) => {
      fail && fail(err);
    }
  });
}

// POST 请求方法
function post(url, data, success, fail) {
  wx.request({
    url: baseUrl + url,
    method: 'POST',
    data: data,
    success: (res) => {
      if (res.statusCode >= 200 && res.statusCode < 300) {
        success && success(res);
      } else {
        fail && fail({
          statusCode: res.statusCode,
          data: res.data
        });
      }
    },
    fail: (err) => {
      fail && fail(err);
    }
  });
}

// 导出两个方法
module.exports = { get, post };