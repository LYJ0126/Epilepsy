from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
import os
import logging
import json
import hashlib
import argparse
import psutil  
import base64
import requests


load_dotenv()


# 配置鉴权 Token（与物联网平台设置相同）
IOT_PLATFORM_TOKEN = "njunju"

# 创建 Flask 应用
app = Flask(__name__)

#DEEPSEEK
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
SYSTEM_PROMPT = """
你是一名专业的癫痫健康顾问，请按照以下要求回答用户问题：

1. 思维链分析：
   - 理解用户问题：识别关键词和核心关注点
   - 风险级别评估：将情况分为绿色（常规问题）、黄色（需关注）和红色（紧急情况）
   - 医学知识检索：使用最新的癫痫医学知识
   - 多角度分析：药物、生活习惯、饮食、压力管理等

2. 回答结构：
   [风险级别]
   [核心建议]
   [详细分析]（按以下顺序）：
   - 药物建议（若适用）
   - 生活调整
   - 紧急处理步骤（如涉及）
   - 何时就医
   [提示]：记住我不能替代专业医生，最后建议咨询神经科专家

3. 安全准则：
   - 避免给出具体药物剂量建议
   - 对紧急情况明确提示立即就医
   - 语言温和、专业、鼓励性
   - 使用简单易懂的术语解释医学术语

4. 特别针对癫痫患者的提示：
   - 强调规律服药的重要性
   - 提醒避免常见诱因（闪光、压力等）
   - 说明急救处理方法
   - 鼓励记录癫痫日记
"""
# 配置命令行参数
parser = argparse.ArgumentParser(description='Epilepsy Health Monitoring Server')
parser.add_argument('--debug', action='store_true', help='Enable debug mode')
parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
args = parser.parse_args()

# 设置调试模式
DEBUG_MODE = args.debug or os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
)
logger = logging.getLogger(__name__)

# 请求历史记录（用于调试）
REQUEST_HISTORY = []
MAX_HISTORY = 10  # 保存最近10个请求

# 打印 POST 请求报文的函数
def print_post_request(request):
    """打印完整的 POST 请求报文"""
    if not DEBUG_MODE:
        return
    
    # 创建报文字符串
    debug_output = []
    debug_output.append("\n" + "="*80)
    debug_output.append("DEBUG: 完整 POST 请求报文")
    debug_output.append("="*80)
    
    # 请求行
    debug_output.append(f"{request.method} {request.path} {request.environ.get('SERVER_PROTOCOL')}")
    
    # 请求头
    debug_output.append("\n请求头:")
    for key, value in request.headers.items():
        debug_output.append(f"{key}: {value}")
    
    # 请求体
    debug_output.append("\n请求体:")
    if request.content_type == 'application/json':
        try:
            body = request.get_json()
            debug_output.append(json.dumps(body, indent=2, ensure_ascii=False))
        except:
            debug_output.append(request.data.decode('utf-8'))
    else:
        try:
            debug_output.append(request.data.decode('utf-8'))
        except UnicodeDecodeError:
            debug_output.append(f"<二进制数据，长度: {len(request.data)} 字节>")
    
    debug_output.append("="*80 + "\n")
    
    # 打印到控制台
    print("\n".join(debug_output))
    
    # 保存到历史记录
    REQUEST_HISTORY.append({
        'timestamp': datetime.utcnow().isoformat(),
        'method': request.method,
        'path': request.path,
        'headers': dict(request.headers),
        'body': request.data.decode('utf-8', errors='replace') if request.data else None
    })
    
    # 保持历史记录大小
    if len(REQUEST_HISTORY) > MAX_HISTORY:
        REQUEST_HISTORY.pop(0)

# 获取最近请求的函数
def get_recent_requests():
    """返回最近的请求历史"""
    return REQUEST_HISTORY

# 创建签名验证装饰器
def iot_signature_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 获取请求头中的鉴权参数
        signature = request.headers.get('Signature')
        timestamp = request.headers.get('Timestamp')
        nonce = request.headers.get('Nonce')
        echostr = request.headers.get('Echostr')
        
        # 记录鉴权信息
        logger.debug(f"鉴权参数: Signature={signature}, Timestamp={timestamp}, Nonce={nonce}, Echostr={echostr}")
        
        # 验证必要参数是否存在
        if not all([signature, timestamp, nonce]):
            logger.warning("缺少鉴权参数")
            return jsonify({
                'success': False,
                'message': 'Missing authentication parameters'
            }), 401
        
        # 验证签名
        if not verify_signature(signature, timestamp, nonce):
            logger.warning("签名验证失败")
            return jsonify({
                'success': False,
                'message': 'Invalid signature'
            }), 403
        
        # 如果是 GET 请求且有 Echostr，需要返回 Echostr
        if request.method == 'GET' and echostr:
            logger.info("服务地址校验请求")
            return echostr, 200, {'Content-Type': 'text/plain'}
        
        # 继续处理请求
        return f(*args, **kwargs)
    return decorated_function

# 签名验证函数
def verify_signature(signature, timestamp, nonce):
    """验证腾讯物联网平台的签名"""
    # 将 Token、Timestamp、Nonce 排序后拼接
    params = [IOT_PLATFORM_TOKEN, timestamp, nonce]
    params.sort()
    raw_string = ''.join(params)
    
    # 计算 SHA1 哈希
    calculated_signature = hashlib.sha1(raw_string.encode('utf-8')).hexdigest()
    
    # 调试日志
    logger.debug(f"计算签名: {calculated_signature}")
    logger.debug(f"接收签名: {signature}")
    
    # 安全比较签名
    return calculated_signature == signature



@app.before_request
def log_request_info():
    logger.debug(f"请求方法: {request.method}")
    logger.debug(f"请求路径: {request.path}")
    logger.debug(f"请求源: {request.remote_addr}")
    logger.debug(f"请求头: {dict(request.headers)}")
    
    # 对于 POST 请求记录请求体
    if request.method == 'POST':
        try:
            body = request.get_json()
            logger.debug(f"请求体: {json.dumps(body, indent=2)}")
        except:
            logger.debug(f"请求体: {request.data.decode('utf-8')}")



# 配置数据库
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "health_data.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 创建 SQLAlchemy 实例并绑定到应用
db = SQLAlchemy(app)

# 定义用户模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def check_password(self, password):
        return self.password == password

# 定义健康数据模型
class HealthData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(50))
    gender = db.Column(db.String(10))
    age = db.Column(db.Integer)
    height = db.Column(db.Float)
    weight = db.Column(db.Float)
    blood_type = db.Column(db.String(5))
    last_update = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<HealthData for user {self.user_id}>'
        
        
class DeviceData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_name = db.Column(db.String(80), nullable=False)
    product_id = db.Column(db.String(50))
    seq = db.Column(db.Integer)
    topic = db.Column(db.String(120))
    
    # 特别添加癫痫状态和位置字段
    epilepsy_state = db.Column(db.Integer)  # 0-正常, 1-癫痫发作
    location = db.Column(db.String(255))   # 地理位置信息
    
    timestamp = db.Column(db.DateTime, nullable=False)
    received_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    def __repr__(self):
        return f'<DeviceData {self.device_name} - {self.timestamp}>'

# 添加用户与设备关联模型
class UserDevice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    device_id = db.Column(db.String(80), nullable=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

@app.route('/register', methods=['POST'])
def register():
    try:
        logger.debug("收到注册请求")
        data = request.json
        
        if not data:
            logger.error("请求体为空")
            return jsonify({
                'success': False,
                'message': '请求体不能为空'
            }), 400
        
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            logger.error("用户名或密码为空")
            return jsonify({
                'success': False,
                'message': '用户名和密码不能为空'
            }), 400
        
        # 检查用户名是否已存在
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            logger.warning(f"用户名已存在: {username}")
            return jsonify({
                'success': False,
                'message': '用户名已存在'
            }), 400
        
        # 创建新用户
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        
        logger.info(f"用户注册成功: {username}")
        return jsonify({
            'success': True,
            'message': '注册成功',
            'user_id': new_user.id
        })
            
    except Exception as e:
        logger.error(f"注册处理异常: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': '服务器内部错误'
        }), 500


# 登录接口
@app.route('/login', methods=['POST'])
def login():
    try:
        logger.debug("收到登录请求")
        data = request.json
        logger.debug(f"请求数据: {data}")
        
        if not data:
            logger.error("请求体为空")
            return jsonify({
                'success': False,
                'message': '请求体不能为空'
            }), 400
        
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            logger.error("用户名或密码为空")
            return jsonify({
                'success': False,
                'message': '用户名和密码不能为空'
            }), 400
        
        logger.debug(f"查找用户: {username}")
        
        # 直接查询数据库
        user = User.query.filter_by(username=username).first()
        
        if not user:
            logger.warning(f"用户不存在: {username}")
            return jsonify({
                'success': False,
                'message': '用户名或密码错误'
            }), 401
        
        logger.debug(f"验证用户密码: {username}")
        if user.check_password(password):
            logger.info(f"用户登录成功: {username}")
            return jsonify({
                'success': True,
                'message': '登录成功',
                'user_id': user.id
            })
        else:
            logger.warning(f"密码错误: {username}")
            return jsonify({
                'success': False,
                'message': '用户名或密码错误'
            }), 401
            
    except Exception as e:
        logger.error(f"登录处理异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '服务器内部错误'
        }), 500

# 获取健康数据接口
@app.route('/health-data', methods=['GET'])
def get_health_data():
    try:
        logger.debug("收到获取健康数据请求")
        user_id = request.args.get('user_id')
        
        if not user_id:
            logger.error("缺少用户ID参数")
            return jsonify({'error': '缺少用户ID'}), 400
        
        logger.debug(f"查找用户 {user_id} 的健康数据")
        
        health_data = HealthData.query.filter_by(user_id=user_id).first()
        
        if health_data:
            logger.info(f"找到用户 {user_id} 的健康数据")
            return jsonify({
                'name': health_data.name,
                'gender': health_data.gender,
                'age': health_data.age,
                'height': health_data.height,
                'weight': health_data.weight,
                'blood_type': health_data.blood_type,
                'last_update': health_data.last_update.strftime('%Y-%m-%d')
            })
        else:
            logger.warning(f"未找到用户 {user_id} 的健康数据")
            return jsonify({'message': '未找到健康数据'}), 404
            
    except Exception as e:
        logger.error(f"获取健康数据异常: {str(e)}")
        return jsonify({
            'error': '服务器内部错误'
        }), 500

# 保存健康数据接口
@app.route('/save-health-data', methods=['POST'])
def save_health_data():
    try:
        logger.debug("收到保存健康数据请求")
        data = request.json
        logger.debug(f"请求数据: {data}")
        
        if not data:
            logger.error("请求体为空")
            return jsonify({'error': '请求体不能为空'}), 400
        
        user_id = data.get('user_id')
        health_data = data.get('health_data')
        
        if not user_id or not health_data:
            logger.error("缺少必要参数")
            return jsonify({'error': '缺少必要参数'}), 400
        
        logger.debug(f"查找用户 {user_id} 的健康数据记录")
        
        record = HealthData.query.filter_by(user_id=user_id).first()
        
        if not record:
            logger.info(f"为用户 {user_id} 创建新的健康数据记录")
            record = HealthData(user_id=user_id)
        
        # 更新数据
        logger.debug("更新健康数据字段")
        record.name = health_data.get('name')
        record.gender = health_data.get('gender')
        record.age = health_data.get('age')
        record.height = health_data.get('height')
        record.weight = health_data.get('weight')
        record.blood_type = health_data.get('bloodType')
        record.last_update = datetime.utcnow()
        
        # 保存到数据库
        logger.debug("保存到数据库")
        db.session.add(record)
        db.session.commit()
        
        logger.info(f"用户 {user_id} 的健康数据保存成功")
        return jsonify({
            'success': True,
            'message': '健康数据保存成功',
            'last_update': record.last_update.strftime('%Y-%m-%d')
        })
        
    except Exception as e:
        logger.error(f"保存健康数据异常: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': '服务器内部错误'
        }), 500


# 物联网数据接收接口 - 专门处理来自 L610 设备的数据
@app.route('/lotdata', methods=['POST','GET'])
@iot_signature_required # 添加鉴权装饰器
def receive_lotdata():
    # 如果是 POST 请求，打印完整报文
    if request.method == 'POST' and DEBUG_MODE:
        print_post_request(request)
        
    if request.method == 'GET':
        logger.info("接收到物联网平台健康检查请求")
        return jsonify({
            'status': 'active',
            'service': 'epilepsy-data-receiver',
            'version': '1.0',
            'api_docs': 'https://epilepsy.host/api-docs',
            'supported_methods': ['POST']
        })

    try:
        logger.debug("收到腾讯物联网平台数据")
        
        # 记录原始请求数据用于调试
        raw_data = request.data.decode('utf-8')
        logger.debug(f"原始请求数据: {raw_data}")
        
        # 尝试解析 JSON
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError as e:
            logger.error(f"无法解析 JSON 数据: {str(e)}")
            return jsonify({
                'success': False,
                'message': 'Invalid JSON format'
            }), 400
        
        logger.debug(f"解析后的数据: {json.dumps(data, indent=2)}")
        
        # 验证基本字段
        required_fields = ['devicename', 'payload', 'timestamp']
        if not all(field in data for field in required_fields):
            missing = [field for field in required_fields if field not in data]
            logger.error(f"缺少必要字段: {missing}")
            return jsonify({
                'success': False,
                'message': f'Missing required fields: {", ".join(missing)}'
            }), 400
        
        # 提取基本数据
        device_name = data['devicename']
        timestamp = datetime.utcfromtimestamp(data['timestamp'])
        product_id = data.get('productid', '')
        seq = data.get('seq', 0)
        topic = data.get('topic', '')
        
        # 提取核心参数 - epilepsy_state 和 location
        payload = data['payload']
        params = payload.get('params', {})
        
        # 解析函数 - 处理 userid*时间戳*值 格式
        def parse_value(field_value):
            if not field_value:
                return None
                
            # 检查是否包含用户ID信息
            if '*' in field_value and len(field_value.split('*')) >= 3:
                parts = field_value.split('*')
                try:
                    user_id = int(parts[0])  # 第一部分是用户ID
                    # 最后部分是实际值，中间部分可以忽略（时间戳）
                    actual_value = parts[-1]
                    # 处理癫痫状态值（可能是字符串或整数）
                    if actual_value in ('0', '1'):
                        actual_value = int(actual_value)
                    return user_id, actual_value
                except (ValueError, IndexError):
                    # 解析失败，返回原始值
                    return None, field_value
            else:
                # 如果不是指定格式，返回原始值
                return None, field_value
                
        epilepsy_state = params.get('epilepsy_state')
        location = params.get('location')

        flag = False
        id = -1
        state = -1
        loc = None

        if epilepsy_state is None:
            logger.warning(f"设备 {device_name} 缺少 epilepsy_state 参数")
        else:
            id,state = parse_value(epilepsy_state)
            data = DeviceData.query.filter_by(user_id=id).first()
            if(data):
                data.epilepsy_state = state
                data.product_id=product_id
                data.seq=seq
                data.topic=topic
                data.timestamp=timestamp
                db.session.commit()
                flag = True


        if location is None:
            logger.warning(f"设备 {device_name} 缺少 location 参数")
        else:
            id,loc = parse_value(location)
            data = DeviceData.query.filter_by(user_id=id).first()
            if(data):
                data.location = loc
                data.product_id=product_id
                data.seq=seq
                data.topic=topic
                data.timestamp=timestamp
                db.session.commit()
                flag = True
            
        if(not flag):
            # 创建新的设备数据记录
            new_record = DeviceData(
                device_name=device_name,
                product_id=product_id,
                seq=seq,
                topic=topic,
                epilepsy_state=state,
                location=loc,
                timestamp=timestamp,
                user_id = id
            )
        
        # 检查是否有用户关联此设备
        #user_device = UserDevice.query.filter_by(device_id=device_name).first()
        #if user_device:
        #    new_record.user_id = user_device.user_id
        #    logger.info(f"设备 {device_name} 关联用户: {user_device.user_id}")
            
        
            # 保存到数据库
            db.session.add(new_record)
            db.session.commit()
        
        logger.info(f"成功接收设备 {device_name} 的数据")
        logger.debug(f"epilepsy_state: {epilepsy_state}, location: {location}")
        
        return jsonify({
            'success': True,
            'message': 'Data received successfully',
            'device_name': device_name
        })
        
    except Exception as e:
        logger.error(f"处理物联网数据异常: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Server error'
        }), 500

# 设备绑定接口
@app.route('/api/bind-device', methods=['POST'])
def bind_device():
    try:
        logger.debug("收到设备绑定请求")
        data = request.json
        
        if not data:
            logger.error("绑定请求体为空")
            return jsonify({'success': False, 'message': 'Empty payload'}), 400
        
        user_id = data.get('user_id')
        device_id = data.get('device_id')
        
        if not user_id or not device_id:
            logger.error("绑定请求缺少必要参数")
            return jsonify({'success': False, 'message': 'Missing user_id or device_id'}), 400
        
        # 检查设备是否已被其他用户绑定
        existing_binding = UserDevice.query.filter_by(device_id=device_id).first()
        if existing_binding:
            logger.warning(f"设备 {device_id} 已被用户 {existing_binding.user_id} 绑定")
            return jsonify({
                'success': False,
                'message': 'Device already bound to another user'
            }), 400
        
        # 创建新的绑定关系
        new_device = UserDevice(
            user_id=user_id,
            device_id=device_id
        )
        
        db.session.add(new_device)
        db.session.commit()
        
        logger.info(f"成功绑定设备 {device_id} 到用户 {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Device bound successfully'
        })
        
    except Exception as e:
        logger.error(f"设备绑定异常: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': 'Server error'
        }), 500
        
# 错误处理
@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"404错误: {error}")
    return jsonify({
        'error': '未找到资源',
        'message': '请求的URL不存在'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500错误: {error}")
    return jsonify({
        'error': '内部服务器错误',
        'message': '请稍后再试'
    }), 500


class EEGWaveform(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    waveform_data = db.Column(db.Text, nullable=False)  # 存储Base64编码的波形图
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 添加新的API端点处理电脑端波形图上传并接收到服务器
@app.route('/upload-waveform', methods=['POST'])
@iot_signature_required
def upload_waveform():
    try:
        data = request.json
        user_id = data.get('user_id')
        waveform_base64 = data.get('waveform_data')
        
        if not user_id or not waveform_base64:
            return jsonify({'success': False, 'message': '缺少必要参数'}), 400
        
        # 清理Base64数据（去除可能的header）
        if waveform_base64.startswith('data:image'):
            waveform_base64 = waveform_base64.split(',', 1)[1]
        
        # 查找用户现有的波形图记录
        existing_waveform = EEGWaveform.query.filter_by(user_id=user_id).first()
        
        if existing_waveform:
            # 更新现有记录
            existing_waveform.waveform_data = waveform_base64
            existing_waveform.created_at = datetime.utcnow()
            db.session.commit()
            logger.info(f"更新用户 {user_id} 的脑电波形图")
        else:
            # 创建新记录
            new_waveform = EEGWaveform(
                user_id=user_id,
                waveform_data=waveform_base64
            )
            db.session.add(new_waveform)
            db.session.commit()
            logger.info(f"创建用户 {user_id} 的脑电波形图")
        
        '''
        # ===== 新增 Base64 转 PNG 存储 ====
        # 注意这个只是测试用的，看从电脑传过来的数据是否正确
        
        # 配置存储路径
        WAVEFORM_SAVE_DIR = "/var/www/epilepsy.host/static/waveforms/"
        
        # 确保目录存在
        if not os.path.exists(WAVEFORM_SAVE_DIR):
            os.makedirs(WAVEFORM_SAVE_DIR, mode=0o755, exist_ok=True)
        
        # 生成唯一文件名
        file_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"eeg_{user_id}_{file_timestamp}.png"
        file_path = os.path.join(WAVEFORM_SAVE_DIR, filename)
        
        # 处理Base64数据（去除可能的header）
        if waveform_base64.startswith('data:image'):
            waveform_base64 = waveform_base64.split(',', 1)[1]
        
        # 解码并保存
        try:
            image_data = base64.b64decode(waveform_base64)
            with open(file_path, "wb") as img_file:
                img_file.write(image_data)
            logger.info(f"已保存脑电图: {file_path}")
        except Exception as e:
            logger.error(f"保存脑电图失败: {str(e)}")
        # ===== 新增结束 =====
        '''
            
        return jsonify({
            'success': True,
            'message': '波形图上传成功',
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        logger.error(f"波形图上传异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '服务器内部错误'
        }), 500
        
# 新增API端点：获取用户(微信小程序)的脑电波形图请求，并返回最新的波形图数据
@app.route('/api/get-waveform', methods=['GET'])
def get_waveform():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户ID'}), 400
        
        # 获取用户最新的波形图记录
        waveform = EEGWaveform.query.filter_by(user_id=user_id)\
            .order_by(EEGWaveform.created_at.desc()).first()
        
        if not waveform:
            return jsonify({
                'success': False,
                'message': '未找到脑电波形图数据'
            }), 404
        
        return jsonify({
            'success': True,
            'waveform_data': waveform.waveform_data,
            'created_at': waveform.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        logger.error(f"获取波形图异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '服务器内部错误'
        }), 500


# 环形队列存储模型
class EEGWaveformQueue(db.Model):
    """脑电波形图环形队列存储"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    waveform_data = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    sequence_id = db.Column(db.Integer, nullable=False)  # 序列ID用于排序

# 更新上传接口 - 实现环形队列
@app.route('/realtime-upload-waveform', methods=['POST'])
@iot_signature_required
def realtime_upload_waveform():
    try:
        data = request.json
        user_id = data.get('user_id')
        waveform_base64 = data.get('waveform_data')
        
        if not user_id or not waveform_base64:
            return jsonify({'success': False, 'message': '缺少必要参数'}), 400
        
        # 清理Base64数据（去除可能的header）
        if waveform_base64.startswith('data:image'):
            waveform_base64 = waveform_base64.split(',', 1)[1]
        
        # 获取当前用户的最新序列ID
        last_record = EEGWaveformQueue.query.filter_by(user_id=user_id)\
            .order_by(EEGWaveformQueue.sequence_id.desc()).first()
        next_id = last_record.sequence_id + 1 if last_record else 1
        
        # 创建新记录
        new_waveform = EEGWaveformQueue(
            user_id=user_id,
            waveform_data=waveform_base64,
            sequence_id=next_id
        )
        db.session.add(new_waveform)
        
        # 维护队列大小（最多保留5张图片）
        if next_id > 10:
            # 删除最旧的记录
            oldest = EEGWaveformQueue.query.filter_by(user_id=user_id)\
                .order_by(EEGWaveformQueue.sequence_id.asc()).first()
            if oldest:
                db.session.delete(oldest)
                logger.info(f"删除用户 {user_id} 的最旧波形图记录，序列ID: {oldest.sequence_id}")
        
        db.session.commit()
        logger.info(f"添加用户 {user_id} 的脑电波形图到队列，序列ID: {next_id}")
        
        return jsonify({
            'success': True,
            'message': '波形图上传成功',
            'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        logger.error(f"波形图上传异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '服务器内部错误'
        }), 500

# 更新获取接口 - 返回最新图像并清理旧图
@app.route('/api/get-latest-waveform', methods=['GET'])
def get_latest_waveform():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户ID'}), 400
        
        # 获取用户最新的波形图记录
        waveform = EEGWaveformQueue.query.filter_by(user_id=user_id)\
            .order_by(EEGWaveformQueue.sequence_id.desc()).first()
        
        if not waveform:
            return jsonify({
                'success': False,
                'message': '未找到脑电波形图数据'
            }), 404
        
        # 删除该用户所有旧的波形图（保留最新）
        EEGWaveformQueue.query.filter_by(user_id=user_id)\
            .filter(EEGWaveformQueue.id < waveform.id).delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'waveform_data': waveform.waveform_data,
            'created_at': waveform.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        logger.error(f"获取波形图异常: {str(e)}")
        return jsonify({
            'success': False,
            'message': '服务器内部错误'
        }), 500
        
# 启用清理端点
@app.route('/clean-waveform', methods=['POST'])
@iot_signature_required
def clean_waveform():
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户ID'}), 400
        
        # 执行批量删除
        deleted_count = EEGWaveformQueue.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        
        logger.info(f"清理用户 {user_id} 的脑电波形图，删除记录数: {deleted_count}")
        
        return jsonify({
            'success': True,
            'message': f'已删除{deleted_count}条记录',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        logger.error(f"数据清理异常: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': '服务器内部错误'
        }), 500

@app.route('/api/epilepsy-consult', methods=['POST'])
def epilepsy_consult():
    user_question = request.json.get('question', '')
    
    if not user_question:
        return jsonify({"error": "问题不能为空"}), 400
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_question}
        ],
        "temperature": 0.3,
        "max_tokens": 1024
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        ai_response = response.json()["choices"][0]["message"]["content"]
        
        return jsonify({
            "answer": ai_response,
            "structured_answer": extract_structured_answer(ai_response)
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def extract_structured_answer(answer_text):
    return {
        "risk_level": extract_section(answer_text, "[风险级别]"),
        "main_advice": extract_section(answer_text, "[详细分析]"),
        "detailed_analysis": extract_section(answer_text, "[核心建议]"),
        "note": extract_section(answer_text, "[提示]")
    }

def extract_section(text, section_header):
    start_idx = text.find(section_header)
    if start_idx == -1:
        return ""
    
    start_idx += len(section_header)
    end_idx = text.find("[", start_idx)
    if end_idx == -1:
        return text[start_idx:].strip()
    
    return text[start_idx:end_idx].strip()

# 在应用入口处创建表格
if __name__ == '__main__':
    # 确保数据库表已创建
    with app.app_context():
        logger.info("创建数据库表")
        db.create_all()
        
        # 创建测试用户（如果不存在）
        if not User.query.filter_by(username='test').first():
            logger.info("创建测试用户")
            test_user = User(username='test', password='123456')
            db.session.add(test_user)
            db.session.commit()
        
        # 确保新表已创建
        for model in [DeviceData, UserDevice]:
            try:
                model.__table__.create(db.engine, checkfirst=True)
                logger.info(f"已创建 {model.__name__} 表")
            except Exception as e:
                logger.warning(f"创建 {model.__name__} 表失败: {str(e)}")
    
    # 启动应用
    logger.info("启动Flask应用")
    app.run(host='0.0.0.0', port=5000, debug=True)

