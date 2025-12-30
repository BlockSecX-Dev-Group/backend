import os
import sys
import re
import traceback
import subprocess  # 新增：调用ffprobe
import json       # 新增：解析ffprobe返回的JSON

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from main.models.database import db
from main.models.VideoInfo import VideoInfo
from main.models.VideoSequence import VideoSequence
from main.managers.Config import Config
from datetime import datetime, timezone

def get_video_duration(video_path):
    """
    用ffprobe获取视频真实时长（秒），兼容mp4/avi/mov等格式
    :param video_path: 视频文件绝对路径
    :return: 视频时长（秒），失败返回600（默认10分钟）
    """
    try:
        # ffprobe命令：输出JSON格式的视频时长
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            video_path
        ]
        # 执行命令并捕获输出
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT, encoding='utf-8')
        # 解析JSON
        duration_data = json.loads(result)
        duration = float(duration_data['format']['duration'])
        # 四舍五入为整数秒
        return int(round(duration))
    except subprocess.CalledProcessError as e:
        print(f"【警告】解析{video_path}时长失败（ffprobe执行错误）：{e.output}")
        return 600  # 默认10分钟
    except (KeyError, ValueError) as e:
        print(f"【警告】解析{video_path}时长失败（格式错误）：{str(e)}")
        return 600
    except Exception as e:
        print(f"【警告】解析{video_path}时长失败：{str(e)}")
        return 600

def init_video_data():
    try:
        # 强制指定视频目录
        VIDEO_ROOT = "/data/Web3_CTF_videos"
        
        # 检查目录是否存在
        if not os.path.exists(VIDEO_ROOT):
            os.makedirs(VIDEO_ROOT, exist_ok=True)
            print(f"【提示】视频目录不存在，已创建：{VIDEO_ROOT}")
            return
        
        # 读取目录内所有文件
        all_files = os.listdir(VIDEO_ROOT)
        
        # 筛选符合Day\d+_xxx.mp4格式的视频文件
        video_files = []
        for filename in all_files:
            if re.match(r'Day\d+_.+\.(mp4|avi|mov)', filename, re.IGNORECASE):
                video_files.append(filename)
        
        if not video_files:
            print(f"【提示】{VIDEO_ROOT}目录下无符合规则的视频文件")
            return
        
        # 按Day后的数字升序排序
        def extract_day_num(filename):
            match = re.search(r'Day(\d+)', filename)
            return int(match.group(1)) if match else 999
        video_files.sort(key=extract_day_num)
        
        # 写入数据库
        for idx, filename in enumerate(video_files, 1):
            video_id = os.path.splitext(filename)[0]
            
            # 跳过已存在的视频（如果需要更新时长，可注释这行）
            existing_video = VideoInfo.query.filter_by(video_id=video_id).first()
            if existing_video:
                # 可选：更新已有视频的时长（如果之前是0）
                if existing_video.video_duration == 0:
                    video_path = os.path.join(VIDEO_ROOT, filename)
                    duration = get_video_duration(video_path)
                    existing_video.video_duration = duration
                    # existing_video.update_time = datetime.now(timezone.utc)  # 新增update_time字段（需在VideoInfo模型中添加）
                    db.session.add(existing_video)
                    print(f"【更新】视频{video_id}时长：{duration}秒")
                continue
            
            # 拼接绝对路径
            video_path = os.path.join(VIDEO_ROOT, filename)
            # 核心修复：调用get_video_duration获取真实时长（不再硬编码为0）
            duration = get_video_duration(video_path)
            
            # 创建视频记录
            video = VideoInfo(
                video_id=video_id,
                video_name=filename,
                video_path=video_path,
                video_duration=duration,  # 真实时长
                trigger_progress=0.9,
                point_reward=10,
                is_active=True,
                create_time=datetime.now(timezone.utc),
                # update_time=datetime.now(timezone.utc)  # 新增：记录更新时间
            )
            db.session.add(video)
            print(f"【新增】视频{video_id}，时长：{duration}秒")
            
            # 创建视频顺序记录
            if not VideoSequence.query.filter_by(video_id=video_id).first():
                sequence = VideoSequence(
                    video_id=video_id,
                    sequence_num=idx,
                    is_active=True,
                    create_time=datetime.now(timezone.utc)
                )
                db.session.add(sequence)
        
        # 提交数据
        db.session.commit()
        print(f"【成功】视频数据初始化完成，共处理{len(video_files)}个视频")
    except Exception as e:
        db.session.rollback()
        print(f"【错误】视频初始化失败：{str(e)}")
        traceback.print_exc()

def init_video_sequence():
    """重新初始化视频顺序（按文件名数字排序）"""
    try:
        videos = VideoInfo.query.filter_by(is_active=True).all()
        if not videos:
            print(f"【提示】无有效视频，跳过顺序初始化")
            return
        
        # 按文件名数字排序
        def extract_num(video):
            match = re.search(r'(\d+)', video.video_id)
            return int(match.group(1)) if match else 999
        videos.sort(key=extract_num)
        
        # 更新顺序号
        for idx, video in enumerate(videos, 1):
            sequence = VideoSequence.query.filter_by(video_id=video.video_id).first()
            if sequence:
                sequence.sequence_num = idx
                # sequence.update_time = datetime.now(timezone.utc)  # 新增update_time字段（需在VideoSequence模型中添加）
            else:
                sequence = VideoSequence(
                    video_id=video.video_id,
                    sequence_num=idx,
                    is_active=True,
                    create_time=datetime.now(timezone.utc),
                )
                db.session.add(sequence)
        
        db.session.commit()
        print(f"【成功】视频顺序初始化完成，共{len(videos)}个视频")
    except Exception as e:
        db.session.rollback()
        print(f"视频顺序初始化失败：{str(e)}")
        traceback.print_exc()

