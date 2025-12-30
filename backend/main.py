# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from flask_cors import CORS, cross_origin
import os
import jwt
import urllib.parse
from functools import wraps
from web3 import Web3
from eth_account.messages import encode_defunct
import traceback
import requests
import json
import re
from flask_apscheduler import APScheduler
from apscheduler.schedulers.background import BackgroundScheduler

from datetime import datetime, timedelta, timezone
from main.models.database import db
from main.managers.Config import Config
from main.managers.FlagManager import FlagManager
from main.managers.UserManager import UserManager
from main.managers.FieldManager import FieldManager
from main.models.typings import *  # 包含 DecoratorException/ConfigOperationException
from main.models.JWTBlacklist import JWTBlacklist
from main.services.DaemonTask import DaemonTask
from main.services.TokenService import TokenService
from main.models.TargetFieldOpenRecord import TargetFieldOpenRecord

from main.managers.SignInManager import SignInManager
from main.managers.AnswerChallengeManager import AnswerChallengeManager
from main.managers.PointManager import PointManager
from main.managers.RankingManager import RankingManager
from main.managers.NFTManager import NFTManager
from main.models.NFTMintRecord import NFTMintRecord
from main.models.AnswerSession import AnswerSession
from main.models.PointQueryLog import PointQueryLog
from main.managers.VideoPointManager import VideoPointManager
from main.managers.VideoUnlockManager import VideoUnlockManager
from main.models.VideoInfo import VideoInfo
from main.models.VideoSequence import VideoSequence
from main.models.UserVideoWatchRecord import UserVideoWatchRecord
from main.models.UserVideoUnlockRecord import UserVideoUnlockRecord

app = Flask(__name__)



scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()


# 开启题目挑战的计划任务
@scheduler.task('interval', id='auto_submit_expired_session', minutes=1)
def auto_submit_expired_session():
    with app.app_context():  # 手动激活Flask上下文
        # 查询：未提交、未过期标记、但实际已过期的会话
        expired_sessions = AnswerSession.query.filter(
            AnswerSession.is_submitted == False,
            AnswerSession.is_expired == False,
            AnswerSession.expire_at <= datetime.now(timezone.utc)
        ).all()
        
        for session in expired_sessions:
            try:
                # 标记为过期
                session.is_expired = True
                # 自动提交（用户未答题，答案为空字典，奖励为0）
                AnswerChallengeManager.instance().submit_answers(
                    user_address=session.user_address,
                    session_id=session.session_id,
                    user_answers={}  # 空答案 → 答对0题，无奖励
                )
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"自动提交过期会话失败：session_id={session.session_id}，错误：{str(e)}")





# CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://root:" + Config.get_value(
    "MariaDB_password") + "@" + Config.get_value("MariaDB_url")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False



db.init_app(app)



with app.app_context():
    db.create_all()
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from main.managers.VideoInitManager import init_video_data, init_video_sequence
    init_video_data()
    init_video_sequence()


fieldManager = FieldManager()
# 如果后面考虑动态更新，这个就不能做全局初始化，应该直接写到函数里面
tokenService = TokenService()
JWT_SECRET_KEY = Config.get_value("JWT_SECRET_KEY")
BASE_DOMAIN_NAME = Config.get_value("BASE_DOMAIN_NAME")
w3 = Web3()

video_point_manager = VideoPointManager.instance()
video_unlock_manager = VideoUnlockManager.instance()

# ============ AI智能合约审计配置 ============
CLAUDE_API_KEY = Config.get_value("CLAUDE_API_KEY")
CLAUDE_API_URL = 'https://api.anthropic.com/v1/messages'
ETHERSCAN_API_KEY = Config.get_value("ETHERSCAN_API_KEY") or Config.get_value("ARBITRUM_ONE_API_KEY")
AI_AUDIT_COST = 200  # AI审计消耗积分

# 区块链配置
CHAIN_CONFIG = {
    'bsc': {'name': 'BSC', 'chain_id': '56'},
    'eth': {'name': 'Ethereum', 'chain_id': '1'},
    'polygon': {'name': 'Polygon', 'chain_id': '137'},
    'base': {'name': 'Base', 'chain_id': '8453'}
}

# AI审计静态文件目录
AIAGENT_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aiagent')


FIELD_FUNCTION_INTRO = {
    "name": "Web3安全靶场核心功能",
    "desc": "提供Web3场景下的安全靶场创建、管理、解题验证等能力，需消耗代币创建，解题成功可获取奖励",
    "core_features": [
        {
            "feature_id": "create_field",
            "feature_name": "靶场创建",
            "feature_desc": "根据指定靶场类型（如合约漏洞、钓鱼攻击、私钥泄露等）创建专属靶场环境，创建前需扣除对应代币",
            "api_path": "/create_field",
            "api_method": "POST",
            "required_params": ["field_name"],
            "permission": "需登录（JWT鉴权）+ 代币余额充足"
        },
        {
            "feature_id": "shutdown_field",
            "feature_name": "靶场关闭",
            "feature_desc": "关闭用户已创建的靶场环境，释放资源，仅靶场创建者可操作",
            "api_path": "/shutdown_field",
            "api_method": "POST",
            "required_params": ["field_id"],
            "permission": "需登录（JWT鉴权）+ 靶场所有者"
        },
        {
            "feature_id": "check_flag",
            "feature_name": "靶场解题验证",
            "feature_desc": "提交靶场对应的解题Flag，验证是否成功攻克靶场，验证通过可获取代币/Flag奖励",
            "api_path": "/check_flag",
            "api_method": "POST",
            "required_params": ["field_id", "flag"],
            "permission": "需登录（JWT鉴权）+ 已创建对应靶场"
        },
        {
            "feature_id": "query_running_field",
            "feature_name": "运行中靶场查询",
            "feature_desc": "查询当前用户正在运行的靶场信息（ID、名称、访问地址）",
            "api_path": "/get_running_field_for_user",
            "api_method": "GET",
            "required_params": [],
            "permission": "需登录（JWT鉴权）"
        },
        {
            "feature_id": "query_all_fields",
            "feature_name": "可创建靶场列表查询",
            "feature_desc": "查询所有支持创建的靶场类型、对应成本、靶场描述",
            "api_path": "/get_all_fields_info",
            "api_method": "GET",
            "required_params": [],
            "permission": "无需鉴权，公开访问"
        },
        {
            "feature_id": "query_available_fields",
            "feature_name": "用户可创建靶场查询",
            "feature_desc": "根据用户代币余额、权限，查询当前可创建的靶场列表",
            "api_path": "/get_available_fields_for_user",
            "api_method": "GET",
            "required_params": [],
            "permission": "需登录（JWT鉴权）"
        }
    ],
    "notes": [
        "靶场创建后会占用资源，建议使用完毕后及时关闭",
        "不同类型靶场消耗代币数量不同，可通过/get_all_fields_info查询",
        "解题Flag为唯一验证凭证，每个靶场Flag仅可验证一次"
    ]
}



def is_token_blacklisted(token):
    """
    判断jwt是否已经失效
    :param token: jwt
    :return:
    """
    return JWTBlacklist.query.filter_by(token=token).first() is not None

def token_required(f):
    """
    鉴权，并从jwt中获取用户地址
    :param f:
    :return: 用户地址
    """
    try:
        @wraps(f)
        def decorator(*args, **kwargs):
            token = None
            auth_header = request.headers.get('Authorization')

            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]

            if not token:
                return jsonify({
                    "status": "error",
                    "data": {},
                    "message": "Token is missing!"
                })

            try:
                decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])

                if is_token_blacklisted(token):
                    return jsonify({
                        "status": "error",
                        "data": {},
                        "message": "Token is blacklisted."
                    })

                user_address = decoded['user_address']
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "data": {},
                    "message": f"Invalid token: {str(e)}"
                })

            return f(user_address, *args, **kwargs)

        return decorator
    except Exception as e:
        raise DecoratorException("token_required装饰器出错：" + ", ".join(str(arg) for arg in e.args))





@app.route('/', methods=['GET', 'POST'])
def index():
    return "ok"



@app.route('/get_user_balance', methods=['GET'])
@cross_origin()
@token_required
def get_user_balance(user_address):
    user_balance = UserManager.get_user_balance(user_address)
    return jsonify({
            "status": "success",
            "data": {
                "user_balance": user_balance
            },
            "message": "Query successful"
        })

@app.route('/create_field', methods=['POST'])
@cross_origin()
@token_required
def create_field(user_address):
    field_name = request.json.get('field_name')
    field_cost_map = fieldManager.get_field_cost_map()
    if field_name in field_cost_map.keys():
        field_cost = int(field_cost_map[field_name])
        # 使用 PointManager 扣除积分
        deduct_success, deduct_msg = PointManager.instance().deduct_points(user_address, field_cost)
        if deduct_success:
            flag, field_id_or_msg, field_url, field_port = fieldManager.create_field(field_name, user_address)
            if flag:
                return jsonify({
                    "status": "success",
                    "data": {
                        "field_id": field_id_or_msg,
                        "field_url": field_url,
                        "field_port": field_port
                    },
                    "message": "success"
                })
            else:
                # 如果创建失败，退还积分
                PointManager.instance().add_points(user_address, field_cost)
                return jsonify({
                    "status": "error",
                    "data": {},
                    "message": field_id_or_msg
                })
        else:
            return jsonify({
                "status": "error",
                "data": {},
                "message": f"积分不足: {deduct_msg}"
            })
    else:
        return jsonify({
            "status": "error",
            "data": {},
            "message": "Invalid field_name"
        })


@app.route('/check_flag', methods=['POST'])
@cross_origin()
@token_required
def check_flag(user_address):
    field_id = request.json.get('field_id')
    flag = request.json.get('flag')
    res, msg = FlagManager.check_flag(field_id, flag, user_address)
    if res:
        return jsonify({
            "status": "success",
            "data": {},
            "message": msg
        })
    else:
        return jsonify({
            "status": "error",
            "data": {}, 
            "message": msg
        })      

@app.route('/get_all_fields_info', methods=['GET'])
@cross_origin()
def get_all_fields_info():
    all_fields_info = fieldManager.get_all_fields_info()
    return jsonify({
        "status": "success",
        "data": {
            "all_fields_info": all_fields_info
        },
        "message": "Query successful"  
    })

  
  

@app.route('/login', methods=['POST'])
@cross_origin()
def login():  
    # TODO 后续要做真人认证，登录的时候先判断是否注册（就是有登录信息过），单独做一个注册接口验证
    try:
        signature = request.json.get('signature')
        ts = request.json.get('ts')
        message = ts
        signable_message = encode_defunct(text=message)
        user_address = w3.eth.account.recover_message(signable_message, signature=signature)
        token = jwt.encode({'user_address': user_address, 'exp': datetime.utcnow() + timedelta(hours=12)}, JWT_SECRET_KEY,
                       algorithm="HS256")
        user_balance = UserManager.get_user_balance(user_address)
        return jsonify({
            "status": "success",
            "data": {
                "access_token": token,
                "user_balance": user_balance
            },
            "message": "Login successful."
        })
    except:
        return jsonify({
            "status": "error",
            "data": {},
            "message": "Signature information is missing or invalid."
        })


@app.route('/logout', methods=['GET'])
@cross_origin()
def logout():
    try:
        auth_header = request.headers.get('Authorization')
        token = auth_header[7:]

        invalidated_token = JWTBlacklist(token=token, invalidated_at=datetime.utcnow())
        db.session.add(invalidated_token)
        db.session.commit()

        return jsonify({
            "status": "success",
            "data": {},
            "message": "User logged out successfully"
        })
    except:
        return jsonify({
            "status": "error",
            "data": {},
            "message": "Authorization is missing or invalid."
        })

@app.route('/get_available_fields_for_user', methods=['GET'])
@cross_origin()
@token_required
def get_available_fields_for_user(user_address):
    res, available_fields_list, msg = UserManager.get_available_fields_for_user(user_address)
    if res:
        return jsonify({
            "status": "success",
            "data": {
                "available_fields_list": available_fields_list
            },
            "message": msg
        })
    else:
        return jsonify({
            "status": "error",
            "data": {},
            "message": msg
        })


@app.route('/extract_token', methods=['POST'])
@cross_origin()
@token_required
def extract_token(user_address):
    token_amount = request.json.get('token_amount')
    res, tx_hash = tokenService.web2_token_to_web3_token(user_address=user_address, token_amount=token_amount)
    if res:
        return jsonify({
            "status": "success",
            "data": {
                "tx_hash": tx_hash
            },
            "message": "Token extraction successful"
        })
    else:
        return jsonify({
            "status": "error",
            "data": {},
            "message": "Token extraction failed"
        })


@app.route('/recharge_token', methods=['POST'])
@cross_origin()
@token_required
def recharge_token(user_address):
    recharge_amount = request.json.get('recharge_amount')
    receive_address = tokenService.create_recharge_order(user_address=user_address, recharge_amount=recharge_amount)
    return jsonify({
        "status": "success",
        "data": {
            "receive_address": receive_address
            },
        "message": "Recharge order created successfully"
    })


@app.route('/get_user_recharge_history', methods=['POST'])
@cross_origin()
@token_required
def get_user_recharge_history(user_address):
    user_orders = tokenService.get_user_recharge_history(user_address=user_address)
    return jsonify({
        "status": "success",
        "data": {
            "user_orders": user_orders
        },
        "message": "Query successful"
    })


@app.route('/get_recharge_order_info', methods=['POST'])
@cross_origin()
@token_required
def get_recharge_order_info(user_address):
    receive_address = request.json.get('receive_address')
    payment_order = tokenService.get_recharge_order_info(receive_address=receive_address)
    return jsonify({
        "status": "success",
        "data": {
            "payment_order": payment_order
        },
        "message": "Query successful"
    })

@app.route('/shutdown_field', methods=['POST'])
@cross_origin()
@token_required
def shutdown_field(user_address):
    field_id = request.json.get('field_id')

    # 先验证权限，再执行关闭
    target_field = TargetFieldOpenRecord.query.filter_by(field_id=field_id).first()
    if not target_field:
        return jsonify({
            "status": "error",
            "data": {},
            "message": "Field not found"
        })

    if user_address != target_field.user_address:
        return jsonify({
            "status": "error",
            "data": {},
            "message": "The user is not the owner of this field"
        })

    # 权限验证通过后执行关闭
    flag = fieldManager.shutdown_field(field_id)
    if flag:
        target_field.status = "stop"
        db.session.commit()
        return jsonify({
            "status": "success",
            "data": {},
            "message": "Shutdown successful"
        })
    else:
        return jsonify({
            "status": "error",
            "data": {},
            "message": "Shutdown failed"
        })

@app.route('/get_running_field_for_user', methods=['GET'])
@cross_origin()
@token_required
def get_running_field_for_user(user_address):
    res, field_id, field_name, host_port, msg = UserManager.get_running_field_for_user(user_address)
    if res:
        # 构建实际的访问 URL
        if host_port:
            field_url = f"http://{BASE_DOMAIN_NAME}:{host_port}"
        else:
            field_url = ""
        return jsonify({
            "status": "success",
            "data": {
                "field_id": field_id,
                "field_name": field_name,
                "field_url": field_url,
                "field_port": host_port
            },
            "message": msg
        })
    else:
        return jsonify({
            "status": "error",
            "data": {},
            "message": msg
        })


@app.route('/get_and_decrypt_all_private_keys_2014_x7Kp9mWqL3vN8sY2', methods=['GET'])
@cross_origin()
def get_and_decrypt_all_private_keys_2014():
    decrypted_private_keys = tokenService.get_and_decrypt_all_private_keys()
    return jsonify({
        "status": "success",
        "data": decrypted_private_keys,
        "message": "ok"
    })





@app.route('/get_field_function_intro', methods=['GET'])
@cross_origin()
def get_field_function_intro():
    """获取靶场功能介绍（结构化数据，无需鉴权）"""
    return jsonify({
        "status": "success",
        "data": FIELD_FUNCTION_INTRO,
        "message": "查询靶场功能介绍成功"
    })



@app.route('/sign-in', methods=['POST'])
@cross_origin()
@token_required
def sign_in_api(user_address):
    """每日签到接口"""
    success, msg, current_points = SignInManager.instance().daily_sign_in(user_address)
    return jsonify({
        "status": "success" if success else "error",
        "data": {"current_points": current_points},
        "message": msg
    })




@app.route('/get-challenge-questions', methods=['POST'])
@cross_origin()
@token_required
def get_challenge_questions_api(user_address):
    """获取答题题目接口（返回会话ID+过期时间）"""
    request_data = request.get_json(force=True, silent=True) or {}

    try:
        success, session_id, data = AnswerChallengeManager.instance().get_random_questions(user_address)
        return jsonify({
            "status": "success" if success else "error",
            "data": {
                "session_id": session_id if success else "",
                "questions": data.get("questions", []) if success else [],
                "expire_at": data.get("expire_at", "") if success else ""  # 前端展示倒计时
            },
            "message": "获取题目成功（已扣除10积分，答题时效20分钟）" if success else data
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "data": {"session_id": "", "questions": [], "expire_at": ""},
            "message": f"获取题目失败：{str(e)}"
        })

@app.route('/submit-challenge-answers', methods=['POST'])
@cross_origin()
@token_required
def submit_challenge_answers_api(user_address):
    """提交答题结果接口（手动提交，仅一次）"""
    request_data = request.get_json(force=True, silent=True) or {}
    # 获取会话ID + 答题答案
    session_id = request_data.get("session_id")
    user_answers = request_data.get("user_answers", {})
    
    # 1. 校验会话ID
    if not session_id or not isinstance(session_id, str):
        return jsonify({
            "status": "error",
            "data": {"correct_count": 0},
            "message": "参数缺失：session_id不能为空"
        })
    
    # 2. 校验答题答案（手动提交必须有答案）
    if not isinstance(user_answers, dict) or len(user_answers) == 0:
        return jsonify({
            "status": "error",
            "data": {"correct_count": 0},
            "message": "参数错误：user_answers不能为空，且需为字典格式（如{\"1\":\"A\",\"2\":\"B\"}）"
        })
    
    # 3. 校验答题数量
    if len(user_answers) != AnswerChallengeManager.instance().QUESTION_NUM:
        return jsonify({
            "status": "error",
            "data": {"correct_count": 0},
            "message": f"参数错误：需提交{AnswerChallengeManager.instance().QUESTION_NUM}道题答案（当前提交{len(user_answers)}道）"
        })
    
    # 调用提交方法（校验会话+时效+重复）
    success, msg, correct_count = AnswerChallengeManager.instance().submit_answers(user_address, session_id, user_answers)
    return jsonify({
        "status": "success" if success else "error",
        "data": {"correct_count": correct_count},
        "message": msg
    })

@app.route('/get-user-points', methods=['GET'])
@cross_origin()
@token_required
def get_user_points_api(user_address):
    """查询用户积分接口 - 与 token 余额完全隔离，带审计"""
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', '')[:512]

    current_points = PointManager.instance().get_user_points(
        user_address,
        query_source="api",
        client_ip=client_ip,
        user_agent=user_agent,
        audit=True
    )
    return jsonify({
        "status": "success",
        "data": {"current_points": current_points},
        "message": "查询积分成功"
    })


'''视频相关接口处'''

@app.route('/get-sign-in-ranking', methods=['GET'])
@cross_origin()
def get_sign_in_ranking_api():
    """仅获取签到积分排行榜前十名（无需鉴权）- 新增签到天数"""
    try:
        sign_in_ranking = RankingManager.instance().get_sign_in_ranking(limit=10)
        return jsonify({
            "status": "success",
            "data": {"sign_in_ranking": sign_in_ranking},  
            "message": "查询签到排行榜成功"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "data": {},
            "message": f"查询签到排行榜失败：{str(e)}"
        })

@app.route('/get-answer-ranking', methods=['GET'])
@cross_origin()
def get_answer_ranking_api():
    """仅获取答题积分排行榜前十名（无需鉴权）- 新增答题总数、答题次数、总答对数"""
    try:
        answer_ranking = RankingManager.instance().get_answer_ranking(limit=10)
        return jsonify({
            "status": "success",
            "data": {"answer_ranking": answer_ranking},  
            "message": "查询答题排行榜成功"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "data": {},
            "message": f"查询答题排行榜失败：{str(e)}"
        })







# 接口1：视频基础信息总接口（合并所有视频信息/解锁状态/播放链接
@app.route('/video/get-video-all-info', methods=['POST'])
@cross_origin()
@token_required
def get_video_all_info_api(user_address):
    """
    合并功能：
    1. 获取单个/所有视频的详细信息
    2. 返回每个视频的解锁状态
    3. 返回可播放的Nginx链接
    4. 返回是否已领取该视频积分
    请求参数：
    - video_id: 可选，指定单个视频ID；不传则返回所有视频
    """
    try:
        request_data = request.get_json(force=True, silent=True) or {}
        target_video_id = request_data.get('video_id')  # 可选，指定单个视频

        # 跨日解锁检查：如果用户前一天已看完当前最新视频，今天自动解锁下一个
        video_unlock_manager.check_and_unlock_on_new_day(user_address)

        # 1. 获取视频列表（单个/所有）
        if target_video_id:
            # 查询单个视频
            video_info_list = [video_point_manager.get_video_info(target_video_id)]
            video_info_list = [item for item in video_info_list if item[0]]  # 过滤失败项
        else:
            # 查询所有视频，按顺序号排序
            video_db_list = db.session.query(VideoInfo, VideoSequence.sequence_num).\
                join(VideoSequence, VideoInfo.video_id == VideoSequence.video_id).\
                filter(VideoInfo.is_active == True).\
                order_by(VideoSequence.sequence_num).all()
            video_info_list = []
            for video, seq_num in video_db_list:
                success, data, msg = video_point_manager.get_video_info(video.video_id)
                if success:
                    video_info_list.append((success, data, msg))
        
        if not video_info_list:
            return jsonify({
                "status": "error",
                "data": {},
                "message": f"Failed to get video info: {target_video_id}" if target_video_id else "Failed to get all videos info"  # 视频信息获取失败
            }), 404
        
        # 2. 组装完整信息（合并解锁状态/播放链接/积分领取状态）
        NGINX_SERVER = "https://blocksecx.com"
        result_video_list = []
        for success, video_data, msg in video_info_list:
            if not success:
                continue
            
            # 解锁状态
            can_play, unlock_msg = video_unlock_manager.check_can_play(user_address, video_data['video_id'])
            if video_data.get('sort_order', 0) == 1:  # 第一个视频
              has_any_unlock = UserVideoUnlockRecord.query.filter_by(
                  user_address=user_address
              ).first()
              if not has_any_unlock:
                  can_play = True
                  unlock_msg = "Default unlocked"  # 默认解锁
            # 积分领取状态
            is_received = video_point_manager.check_video_point_received(user_address, video_data['video_id'])
            # 播放链接（仅解锁后返回）
            play_url = f"{NGINX_SERVER}/video_files/{video_data['video_name']}" if can_play else ""
            
            result_video_list.append({
                "video_id": video_data['video_id'],
                "video_name": video_data['video_name'],
                "video_duration": video_data.get('video_duration', 0),  # 视频时长
                "point_reward": video_data.get('point_reward', 0),     # 奖励积分
                "sort_order": video_data.get('sort_order', 0),         # 排序序号
                "can_play": can_play,                                  # 是否解锁可播放
                "unlock_msg": unlock_msg,                              # 解锁状态说明
                "play_url": play_url,                                  # Nginx播放链接
                "is_received": is_received,                            # 是否已领积分
                "video_desc": video_data.get('video_desc', '')         # 视频描述（补充）
            })
        
        # 3. 返回是否可解锁下一个视频（全局状态）
        can_unlock_next, unlock_next_msg, _ = video_unlock_manager.check_can_unlock_next(user_address)

        # 4. 检查今日解锁是否已达上限
        is_daily_limit_reached = video_unlock_manager.get_today_unlock_count(user_address) >= video_unlock_manager.DAILY_UNLOCK_LIMIT

        return jsonify({
            "status": "success",
            "data": {
                "video_list": result_video_list,
                "can_unlock_next": can_unlock_next,  # 是否可解锁下一个视频
                "unlock_next_msg": unlock_next_msg,  # 解锁下一个视频的说明
                "is_daily_limit_reached": is_daily_limit_reached  # 今日解锁是否已达上限
            },
            "message": "Video info retrieved successfully"  # 视频信息获取成功
        }), 200
    
    except Exception as e:
        error_msg = f"Failed to get video info: {str(e)}"  # 视频信息获取失败
        print(error_msg)
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "data": {},
            "message": error_msg
        }), 500

@app.route('/video/report-progress-and-unlock', methods=['POST'])
@cross_origin()
@token_required
def report_progress_and_unlock_api(user_address):
    """
    合并功能：
    1. 上报视频观看进度（首次/最终）
    2. 校验通过后自动发放积分
    3. 积分发放后自动解锁下一个视频
    请求参数：
    - video_id: 必传，视频ID
    - watch_record_id: 必传，观看记录ID
    - is_ended: 必传，是否播放结束
    - client_timestamp: 必传，前端时间戳（秒）
    """
    try:
        request_data = request.get_json(force=True, silent=True) or {}
        # 必传参数
        video_id = request_data.get('video_id')
        watch_record_id = request_data.get('watch_record_id')
        is_ended = request_data.get('is_ended', False)
        client_timestamp = int(request_data.get('client_timestamp', 0))
        
        # 1. 基础校验
        if not all([video_id, watch_record_id, client_timestamp]):
            return jsonify({
                "status": "error",
                "data": {"triggered": False, "timestamp": int(datetime.now().timestamp())},
                "message": "video_id, watch_record_id, client_timestamp cannot be empty"  # video_id、watch_record_id、client_timestamp不能为空
            }), 400
        
        # 2. 时间戳校验
        server_timestamp = int(datetime.now().timestamp())
        ts_diff = abs(server_timestamp - client_timestamp)
        if ts_diff > 30:
            return jsonify({
                "status": "error",
                "data": {"triggered": False, "timestamp": server_timestamp},
                "message": f"Timestamp error (diff {ts_diff}s), progress invalid"  # 时间戳异常（时差{ts_diff}秒），进度无效
            }), 400
        
        # 3. 视频信息校验
        video = VideoInfo.query.filter_by(video_id=video_id, is_active=True).first()
        if not video:
            return jsonify({
                "status": "error",
                "data": {"triggered": False, "timestamp": server_timestamp},
                "message": "Video not found"  # 视频不存在
            }), 404
        video_duration = video.video_duration or 600
        if video_duration == 0:
            return jsonify({
                "status": "error",
                "data": {"triggered": False, "timestamp": server_timestamp},
                "message": "Video duration not initialized"  # 视频时长未初始化
            }), 400
        
        # 4. 查找/创建观看记录
        watch_record = UserVideoWatchRecord.query.filter_by(
            user_address=user_address,
            video_id=video_id,
            watch_record_id=watch_record_id
        ).first()
        
        if not watch_record:
            # 首次上报
            watch_record = UserVideoWatchRecord(
                user_address=user_address,
                video_id=video_id,
                watch_record_id=watch_record_id,
                first_client_ts=client_timestamp,
                first_server_ts=server_timestamp,  # 记录服务器时间戳用于防作弊校验
                final_client_ts=0,
                is_rewarded=False
            )
            db.session.add(watch_record)
            db.session.commit()
            return jsonify({
                "status": "success",
                "data": {
                    "triggered": False,
                    "timestamp": server_timestamp,
                    "tip": "First report success, waiting for playback end validation"  # 首次上报成功，等待播放结束校验
                },
                "message": "First timestamp reported successfully"  # 首次时间戳上报成功
            })
        else:
            # 最终上报：校验+发积分+自动解锁下一个视频
            watch_record.final_client_ts = client_timestamp

            # 客户端上报的观看时长
            client_watch_seconds = watch_record.final_client_ts - watch_record.first_client_ts
            # 服务器实际经过的时长（防作弊校验）
            server_elapsed = server_timestamp - watch_record.first_server_ts if watch_record.first_server_ts else client_watch_seconds

            # 校验条件
            watch_threshold_min = video_duration * 0.8  # 80%下限
            watch_threshold_max = video_duration * 5.0  # 500%上限

            # 构建详细的校验失败原因
            fail_reasons = []
            if not is_ended:
                fail_reasons.append("Video not finished playing")  # 视频未播放完成
            if client_watch_seconds < watch_threshold_min:
                fail_reasons.append(f"Watch duration too short (need >={int(watch_threshold_min)}s, actual {int(client_watch_seconds)}s)")  # 观看时长不足
            if client_watch_seconds > watch_threshold_max:
                fail_reasons.append(f"Watch duration abnormal (exceeded {int(watch_threshold_max)}s)")  # 观看时长异常
            # 防作弊：客户端时长与服务器时长差距过大（允许60秒误差）
            if abs(client_watch_seconds - server_elapsed) > 60:
                fail_reasons.append(f"Time validation error (client {int(client_watch_seconds)}s, server {int(server_elapsed)}s)")  # 时间校验异常

            is_qualified = (
                is_ended
                and watch_threshold_min <= client_watch_seconds <= watch_threshold_max
                and abs(client_watch_seconds - server_elapsed) <= 60  # 防作弊
            )

            # 5. 校验通过：发积分 + 标记观看完成 + 自动解锁下一个视频
            unlock_next_success = False
            unlock_next_msg = ""
            if is_qualified and not watch_record.is_rewarded:
                # 发放积分
                video_point_manager.grant_video_point(user_address, video_id)
                watch_record.is_rewarded = True

                # 标记当前视频观看完成（修复：解锁下一个视频前必须先标记当前视频 is_watched=True）
                current_unlock_record = UserVideoUnlockRecord.query.filter_by(
                    user_address=user_address,
                    video_id=video_id
                ).first()
                if current_unlock_record:
                    current_unlock_record.is_watched = True
                    current_unlock_record.watch_complete_time = datetime.now(timezone.utc)
                else:
                    # 第一个视频没有解锁记录，需要创建
                    video_seq = VideoSequence.query.filter_by(video_id=video_id).first()
                    if video_seq:
                        current_unlock_record = UserVideoUnlockRecord(
                            user_address=user_address,
                            video_id=video_id,
                            sequence_num=video_seq.sequence_num,
                            is_unlocked=True,
                            unlock_time=datetime.now(timezone.utc),
                            is_watched=True,
                            watch_complete_time=datetime.now(timezone.utc)
                        )
                        db.session.add(current_unlock_record)

                # 使用 VideoUnlockManager 统一的每日解锁次数统计（排除第一个视频）
                # Use VideoUnlockManager's unified daily unlock count (excludes first video)
                today_unlock_count = video_unlock_manager.get_today_unlock_count(user_address)

                # 若当日未达解锁上限，自动解锁下一个视频
                # If daily limit not reached, auto unlock next video
                if today_unlock_count < video_unlock_manager.DAILY_UNLOCK_LIMIT:
                    unlock_next_success, unlock_next_msg = video_unlock_manager.unlock_next_video(user_address, auto_unlock=True)
                else:
                    unlock_next_success = False
                    unlock_next_msg = f"Daily unlock limit reached ({video_unlock_manager.DAILY_UNLOCK_LIMIT} video per day)"  # 当日解锁次数已达上限

                db.session.commit()
                
                return jsonify({
                    "status": "success",
                    "data": {
                        "triggered": True,
                        "timestamp": server_timestamp,
                        "video_duration": video_duration,
                        "reward_point": video.point_reward,
                        "unlock_next_success": unlock_next_success,
                        "unlock_next_msg": unlock_next_msg
                    },
                    "message": f"Validation passed! Awarded {video.point_reward} points, auto unlock next video: {unlock_next_msg}"  # 校验通过！发放积分，自动解锁下一个视频
                })
            else:
                # 校验失败，返回详细原因
                db.session.commit()
                # 如果已经领过积分，单独提示
                if watch_record.is_rewarded:
                    fail_msg = "Points for this video already claimed, cannot claim again"  # 该视频积分已领取，无法重复领取
                else:
                    fail_msg = "Validation failed: " + "; ".join(fail_reasons) if fail_reasons else "Unknown reason"  # 校验失败 / 未知原因
                return jsonify({
                    "status": "success",
                    "data": {
                        "triggered": False,
                        "timestamp": server_timestamp,
                        "video_duration": video_duration,
                        "unlock_next_success": False,
                        "fail_reasons": fail_reasons  # 返回详细原因列表
                    },
                    "message": fail_msg
                })
    except Exception as e:
        error_msg = f"Progress report failed: {str(e)}"  # 进度上报失败
        print(error_msg)
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "data": {"triggered": False, "timestamp": int(datetime.now().timestamp())},
            "message": error_msg
        }), 500


@app.route('/video/stream/<path:video_id>', methods=['GET', 'HEAD'])
@cross_origin()
@token_required
def stream_video_api(user_address, video_id):
    """兼容旧接口：重定向到Nginx播放"""
    try:
        video_id = urllib.parse.unquote(video_id)
        # 真正播放时更新观看时间
        can_play, msg = video_unlock_manager.check_can_play(user_address, video_id, update_watch_time=True)
        if not can_play:
            return jsonify({"status":"error","data":{},"message":msg}), 403
        
        success, video_data, msg = video_point_manager.get_video_info(video_id)
        if not success:
            return jsonify({"status":"error","data":{},"message":msg}), 404
        
        NGINX_SERVER = "https://blocksecx.com"
        nginx_video_url = f"{NGINX_SERVER}/video_files/{video_data['video_name']}"

        response = Response(status=307)
        response.headers['Location'] = nginx_video_url
        response.headers['Content-Type'] = 'video/mp4'
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    
    except Exception as e:
        error_msg = f"Video playback failed: {str(e)}"  # 视频播放失败
        print(error_msg)
        return jsonify({"status":"error","data":{},"message":error_msg}), 500


# ---------------------------------------------------------

# ==================== 新版 NFT 接口 (EIP-712 Meta-Tx) ====================



# 1. 获取签名参数 (GET)
@app.route('/nft/params', methods=['GET'])
@cross_origin()
@token_required
def get_nft_mint_params_api(user_address):
    try:
        success, result = NFTManager.instance().get_mint_params(user_address)
        if success:
            return jsonify({"status": "success", "data": result, "message": "OK"})
        return jsonify({"status": "error", "message": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# 2. 提交铸造 (POST)
@app.route('/nft/submit', methods=['POST'])
@cross_origin()
@token_required
def submit_nft_mint_api(user_address):
    data = request.get_json(force=True, silent=True) or {}

    signature = data.get("signature")
    nonce = data.get("nonce")
    deadline = data.get("deadline")

    if not all([signature, nonce is not None, deadline]):
        return jsonify({"status": "error", "message": "缺少参数 (signature, nonce, deadline)"})

    try:
        success, result = NFTManager.instance().verify_and_submit_mint(
            user_address, signature, nonce, deadline
        )
        if success:
            return jsonify({
                "status": "success",
                "data": {"tx_hash": result},
                "message": "铸造成功！交易已上链"
            })
        return jsonify({"status": "error", "message": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/nft/history', methods=['GET'])
@cross_origin()
@token_required
def get_nft_history_api(user_address):
    """获取当前用户的 NFT 铸造历史"""
    page = request.args.get('page', 1, type=int)
    size = request.args.get('size', 10, type=int)

    try:
        success, result = NFTManager.instance().get_mint_history(user_address, page, size)

        if success:
            return jsonify({
                "status": "success",
                "data": result,
                "message": "OK"
            })
        return jsonify({"status": "error", "message": result})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# ==================== END ====================















# --------------------------------------------------------------------------
# ============ AI智能合约审计API (整合自aiagent) ============

def build_audit_prompt(address, chain, source_code, honeypot_data):
    """构建审计提示词"""
    chain_name = CHAIN_CONFIG.get(chain, {}).get('name', chain.upper())

    prompt = f"""You are a professional smart contract security auditor. Please perform a comprehensive security audit on the following smart contract.

## Contract Information
- Contract Address: {address}
- Blockchain: {chain_name}

## Honeypot Detection Results
"""

    if honeypot_data and honeypot_data.get('success') != False:
        is_hp = honeypot_data.get('is_honeypot', False)
        prompt += f"""- Is Honeypot: {'Yes ⚠️ HIGH RISK!' if is_hp else 'No ✓'}
- Buy Tax: {float(honeypot_data.get('buy_tax', 0)) * 100:.2f}%
- Sell Tax: {float(honeypot_data.get('sell_tax', 0)) * 100:.2f}%
- Risk Level: {honeypot_data.get('risk_level', 'unknown')}
- Token Name: {honeypot_data.get('token_name', 'Unknown')}
- Token Symbol: {honeypot_data.get('token_symbol', 'Unknown')}
- Holder Count: {honeypot_data.get('holders', 0)}
"""
        if honeypot_data.get('honeypot_reason'):
            prompt += f"- Risk Reason: {honeypot_data['honeypot_reason']}\n"
    else:
        prompt += "- Detection failed, please evaluate carefully\n"

    if source_code:
        if len(source_code) > 30000:
            source_code = source_code[:30000] + "\n\n... (source code truncated due to length)"
        prompt += f"\n## Contract Source Code\n```solidity\n{source_code}\n```\n"
    else:
        prompt += "\n## Contract Source Code\nUnable to retrieve source code. Contract may not be verified.\n"

    prompt += """
## Please output the audit report strictly in the following format (for parsing):

### Risk Score
Risk Score: X/100 (0 = safest, 100 = most dangerous)

**Scoring Rationale:**
1. [Reason 1]
2. [Reason 2]
3. [Reason 3]

### Contract Analysis
Briefly describe the main functionality of this contract (2-3 sentences).

### Security Vulnerabilities

**Critical Risk:**
- **[Vulnerability Name]**: [Detailed description]

**High Risk:**
- **[Vulnerability Name]**: [Detailed description]

**Medium Risk:**
- **[Vulnerability Name]**: [Detailed description]

**Low Risk:**
- **[Vulnerability Name]**: [Detailed description]

(If no vulnerabilities found at a level, write "None detected")

### Honeypot Characteristics Check
For each item, indicate ✓ (Not Found) or ✗ (Found) or ? (Cannot Determine):
| Check Item | Result |
|------------|--------|
| Hidden pause/freeze function | [Result] |
| Blacklist/Whitelist mechanism | [Result] |
| Modifiable tax/fee functions | [Result] |
| Hidden mint function | [Result] |
| Excessive owner privileges | [Result] |
| Anti-bot mechanism | [Result] |
| Max wallet/transaction limits | [Result] |
| Cooldown mechanism | [Result] |

### Privilege Analysis
Analyze the owner/admin privileges of the contract and assess centralization risks.

### Fund Safety Assessment

**Positive Factors:**
1. [Positive factor 1]
2. [Positive factor 2]

**Risk Warnings:**
1. [Risk warning 1]
2. [Risk warning 2]

### Investment Recommendation
Provide a clear conclusion (choose one):
- ✅ **SAFE TO CONSIDER** - Low risk, proceed with caution
- ⚠️ **CAUTION ADVISED** - Medium risk, careful evaluation needed
- ❌ **NOT RECOMMENDED** - High risk, avoid investment

**Summary:** [One sentence summary]

IMPORTANT: Respond ONLY in English. Be professional but easy to understand."""

    return prompt


def parse_ai_response(text, address, chain, honeypot_data, source_code):
    """解析AI响应为结构化JSON"""
    # 提取风险分数
    score_match = re.search(r'Risk\s*Score[:\s]*(\d+)\s*/\s*100|(\d+)\s*/\s*100', text, re.IGNORECASE)
    risk_score = 50
    if score_match:
        risk_score = int(score_match.group(1) or score_match.group(2))

    # 判断风险等级
    if risk_score >= 75:
        risk_level = 'critical'
        verdict = 'dangerous'
    elif risk_score >= 50:
        risk_level = 'high'
        verdict = 'risky'
    elif risk_score >= 25:
        risk_level = 'medium'
        verdict = 'caution'
    else:
        risk_level = 'low'
        verdict = 'safe'

    # 提取投资建议
    if 'NOT RECOMMENDED' in text.upper() or '❌' in text:
        recommendation = 'avoid'
        recommendation_text = 'Not Recommended - High Risk'
    elif 'CAUTION' in text.upper() or '⚠️' in text:
        recommendation = 'caution'
        recommendation_text = 'Caution Advised - Medium Risk'
    elif 'SAFE TO CONSIDER' in text.upper() or '✅' in text:
        recommendation = 'safe_to_invest'
        recommendation_text = 'Safe to Consider - Low Risk'
    else:
        recommendation = 'unknown'
        recommendation_text = 'Further evaluation needed'

    # 提取摘要
    one_line = ""
    summary_patterns = [
        r'\*\*Summary[:\*]*\s*(.+?)(?:\n|$)',
        r'Summary[:\s]+(.+?)(?:\n|$)',
    ]
    for pattern in summary_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            one_line = match.group(1).strip()[:150]
            break

    if not one_line:
        if verdict == 'safe':
            one_line = "Contract shows low risk. Proceed with standard due diligence."
        elif verdict == 'dangerous':
            one_line = "Contract contains serious risks. Avoid investment."
        else:
            one_line = "Contract has some risks. Careful evaluation recommended."

    # 快速检查
    quick_checks = {
        'is_open_source': bool(source_code and len(source_code) > 100),
        'has_pause_function': '✗' in text and 'pause' in text.lower(),
        'has_blacklist': '✗' in text and ('blacklist' in text.lower() or 'whitelist' in text.lower()),
        'has_mint_function': '✗' in text and 'mint' in text.lower(),
        'has_proxy': 'proxy' in text.lower() or 'upgradeable' in text.lower(),
        'owner_can_change_tax': '✗' in text and ('tax' in text.lower() or 'fee' in text.lower()),
        'max_tx_limit': 'max' in text.lower() and ('wallet' in text.lower() or 'transaction' in text.lower()),
        'has_cooldown': 'cooldown' in text.lower()
    }

    # 构建结构化结果
    result = {
        'success': True,
        'timestamp': datetime.now(timezone.utc).isoformat() + 'Z',
        'contract': {
            'address': address,
            'chain': chain,
            'chain_name': CHAIN_CONFIG.get(chain, {}).get('name', chain.upper()),
            'name': honeypot_data.get('token_name', 'Unknown'),
            'symbol': honeypot_data.get('token_symbol', 'Unknown'),
            'verified': bool(source_code and len(source_code) > 100)
        },
        'risk_summary': {
            'score': risk_score,
            'level': risk_level,
            'verdict': verdict,
            'one_line': one_line
        },
        'honeypot_detection': {
            'is_honeypot': honeypot_data.get('is_honeypot', False),
            'buy_tax': round(float(honeypot_data.get('buy_tax', 0)) * 100, 2),
            'sell_tax': round(float(honeypot_data.get('sell_tax', 0)) * 100, 2),
            'holders': honeypot_data.get('holders', 0),
            'risk_level': honeypot_data.get('risk_level', 'unknown'),
            'reason': honeypot_data.get('honeypot_reason', '')
        },
        'quick_checks': quick_checks,
        'investment_advice': {
            'recommendation': recommendation,
            'recommendation_text': recommendation_text,
            'confidence': 100 - risk_score
        },
        'raw_analysis': text
    }

    return result


@app.route('/honeypot/<chain>/<address>')
@cross_origin()
@token_required
def check_honeypot(user_address, chain, address):
    """貔貅币检测 - 需要登录"""
    if chain not in CHAIN_CONFIG:
        return jsonify({'success': False, 'error': 'Unsupported chain'})

    chain_id = CHAIN_CONFIG[chain]['chain_id']

    try:
        url = f"https://api.honeypot.is/v2/IsHoneypot?address={address}&chainID={chain_id}"
        response = requests.get(url, timeout=30)
        data = response.json()

        result = {
            'success': True,
            'is_honeypot': data.get('honeypotResult', {}).get('isHoneypot', False),
            'honeypot_reason': data.get('honeypotResult', {}).get('honeypotReason', ''),
            'buy_tax': data.get('simulationResult', {}).get('buyTax', 0),
            'sell_tax': data.get('simulationResult', {}).get('sellTax', 0),
            'token_symbol': data.get('token', {}).get('symbol', 'Unknown'),
            'token_name': data.get('token', {}).get('name', 'Unknown'),
            'risk_level': data.get('summary', {}).get('risk', 'unknown'),
            'holders': data.get('token', {}).get('totalHolders', 0)
        }
        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/source/<chain>/<address>')
@cross_origin()
@token_required
def get_contract_source(user_address, chain, address):
    """获取合约源码 - 需要登录"""
    if chain not in CHAIN_CONFIG:
        return jsonify({'success': False, 'error': 'Unsupported chain'})

    chain_id = CHAIN_CONFIG[chain]['chain_id']

    try:
        url = f"https://api.etherscan.io/v2/api?chainid={chain_id}&module=contract&action=getsourcecode&address={address}"
        if ETHERSCAN_API_KEY:
            url += f"&apikey={ETHERSCAN_API_KEY}"

        response = requests.get(url, timeout=30)
        data = response.json()

        if data.get('status') == '1' and data.get('result'):
            result = data['result'][0]
            source_code = result.get('SourceCode', '')

            # 处理多文件合约格式
            if source_code.startswith('{{'):
                try:
                    source_code = source_code[1:-1]
                    parsed = json.loads(source_code)
                    sources = parsed.get('sources', {})
                    combined = '\n\n'.join([
                        f"// ========== {name} ==========\n{s.get('content', '')}"
                        for name, s in sources.items()
                    ])
                    source_code = combined
                except:
                    pass

            return jsonify({
                'success': True,
                'source_code': source_code,
                'contract_name': result.get('ContractName', 'Unknown'),
                'compiler_version': result.get('CompilerVersion', ''),
                'abi': result.get('ABI', '')
            })
        else:
            return jsonify({'success': False, 'error': 'Contract not verified', 'source_code': ''})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/audit', methods=['POST', 'OPTIONS'])
@cross_origin()
@token_required
def ai_audit(user_address):
    """AI智能合约审计 - 流式返回，需要登录，消耗200积分"""
    if request.method == 'OPTIONS':
        return '', 204

    # 扣除200积分
    deduct_success, deduct_msg = PointManager.instance().deduct_points(user_address, AI_AUDIT_COST)
    if not deduct_success:
        return jsonify({
            'success': False,
            'error': f'积分不足，需要{AI_AUDIT_COST}积分: {deduct_msg}'
        })

    data = request.json
    address = data.get('address', '')
    chain = data.get('chain', 'bsc')
    source_code = data.get('source_code', '')
    honeypot_data = data.get('honeypot_data', {})

    prompt = build_audit_prompt(address, chain, source_code, honeypot_data)

    def generate():
        try:
            response = requests.post(
                CLAUDE_API_URL,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': CLAUDE_API_KEY,
                    'anthropic-version': '2023-06-01'
                },
                json={
                    'model': 'claude-sonnet-4-20250514',
                    'max_tokens': 4096,
                    'stream': True,
                    'messages': [{'role': 'user', 'content': prompt}]
                },
                stream=True,
                timeout=120
            )

            if response.status_code != 200:
                yield f'data: {{"error": "Claude API错误: {response.status_code}"}}\n\n'
                return

            full_text = ""
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        try:
                            json_str = line[6:]
                            if json_str.strip() == '[DONE]':
                                continue
                            chunk_data = json.loads(json_str)

                            if chunk_data.get('type') == 'content_block_delta':
                                text = chunk_data.get('delta', {}).get('text', '')
                                if text:
                                    full_text += text
                                    yield f'data: {{"choices":[{{"delta":{{"content":"{json.dumps(text)[1:-1]}"}}}}]}}\n\n'
                        except json.JSONDecodeError:
                            pass

            # 解析AI输出为结构化JSON
            structured_result = parse_ai_response(full_text, address, chain, honeypot_data, source_code)
            yield f'data: {{"type":"final_result","result":{json.dumps(structured_result, ensure_ascii=False)}}}\n\n'

        except Exception as e:
            yield f'data: {{"error": "{str(e)}"}}\n\n'

    return Response(generate(), mimetype='text/event-stream')


@app.route('/audit/sync', methods=['POST', 'OPTIONS'])
@cross_origin()
@token_required
def ai_audit_sync(user_address):
    """AI智能合约审计 - 同步返回完整JSON，需要登录，消耗200积分"""
    if request.method == 'OPTIONS':
        return '', 204

    # 扣除200积分
    deduct_success, deduct_msg = PointManager.instance().deduct_points(user_address, AI_AUDIT_COST)
    if not deduct_success:
        return jsonify({
            'success': False,
            'error': f'积分不足，需要{AI_AUDIT_COST}积分: {deduct_msg}'
        })

    data = request.json
    address = data.get('address', '')
    chain = data.get('chain', 'bsc')
    source_code = data.get('source_code', '')
    honeypot_data = data.get('honeypot_data', {})

    prompt = build_audit_prompt(address, chain, source_code, honeypot_data)

    try:
        response = requests.post(
            CLAUDE_API_URL,
            headers={
                'Content-Type': 'application/json',
                'x-api-key': CLAUDE_API_KEY,
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 4096,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=120
        )

        if response.status_code != 200:
            # 审计失败，退还积分
            PointManager.instance().add_points(user_address, AI_AUDIT_COST)
            return jsonify({'success': False, 'error': f'Claude API错误: {response.status_code}'})

        result = response.json()
        full_text = result.get('content', [{}])[0].get('text', '')

        structured_result = parse_ai_response(full_text, address, chain, honeypot_data, source_code)
        return jsonify(structured_result)

    except Exception as e:
        # 审计失败，退还积分
        PointManager.instance().add_points(user_address, AI_AUDIT_COST)
        return jsonify({'success': False, 'error': str(e)})


@app.route('/aiagent/audit.html')
@cross_origin()
def serve_audit_html():
    """提供AI审计前端页面"""
    return send_from_directory(AIAGENT_STATIC_DIR, 'audit.html')


# --------------------------------------------------------------------------



if __name__ == '__main__':
    try:

        print("【启动】开始初始化视频数据...")
        with app.app_context():
            from main.managers.VideoInitManager import init_video_data, init_video_sequence
            init_video_data()
            init_video_sequence()
        print("【启动】视频数据初始化完成！")

        
        if not scheduler.running:
            scheduler.init_app(app)

        scheduler.add_job(
            id='reward_job', 
            func=DaemonTask.distribute_rewards, 
            args=[app], 
            trigger='interval', 
            seconds=60
        )
        scheduler.add_job(
            id='check_and_shutdown_fields', 
            func=DaemonTask.shutdown_field, 
            args=[app], 
            trigger='interval',
            seconds=1
        )
        scheduler.add_job(
            id='check_payment', 
            func=DaemonTask.check_payment, 
            args=[app], 
            trigger='interval', 
            seconds=20,
            max_instances=3
        )
        

        if not scheduler.running:
            scheduler.start()

        app.run(
            host='0.0.0.0', 
            port=5000,
            debug=False,  # 生产环境关闭debug
            threaded=True  # 开启多线程支持视频流
        )
    except Exception as e:
        error_stack = traceback.format_exc()
        with open("error.log", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now(timezone.utc)}] {error_stack}\n")
        raise e