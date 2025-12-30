# -*- coding: utf-8 -*-
"""Video Point Manager / 视频积分管理器"""
from main.models.database import db
from main.models.VideoInfo import VideoInfo
from main.models.VideoSequence import VideoSequence
from main.models.UserVideoPointRecord import UserVideoPointRecord
from main.managers.PointManager import PointManager
from datetime import datetime, timezone

class VideoPointManager:
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_video_info(self, video_id):
        """Get video basic info / 获取视频基础信息"""
        try:
            video = VideoInfo.query.filter_by(video_id=video_id, is_active=True).first()
            if not video:
                return False, {}, "Video not found"  # 视频不存在

            # 获取视频顺序号
            video_seq = VideoSequence.query.filter_by(video_id=video_id).first()
            sort_order = video_seq.sequence_num if video_seq else 0

            data = {
                "video_id": video.video_id,
                "video_name": video.video_name,
                "video_duration": video.video_duration,
                "point_reward": video.point_reward,
                "trigger_progress": video.trigger_progress,
                "sort_order": sort_order,
                "video_desc": getattr(video, 'video_desc', '')
            }
            return True, data, "Retrieved successfully"  # 获取成功
        except Exception as e:
            return False, {}, f"Failed to retrieve: {str(e)}"  # 获取失败

    def check_video_point_received(self, user_address, video_id):
        """Check if user has received points for this video / 检查用户是否已领取该视频积分"""
        try:
            record = UserVideoPointRecord.query.filter_by(
                user_address=user_address,
                video_id=video_id,
                is_received=True
            ).first()
            return record is not None
        except Exception as e:
            return False

    def grant_video_point(self, user_address, video_id):
        """Grant video watching points / 发放视频观看积分"""
        try:
            # 检查是否已领取
            if self.check_video_point_received(user_address, video_id):
                return False, "Points already received"  # 积分已领取

            # 获取视频信息
            video = VideoInfo.query.filter_by(video_id=video_id, is_active=True).first()
            if not video:
                return False, "Video not found"  # 视频不存在

            # 发放积分
            success, result = PointManager.instance().add_points(user_address, video.point_reward)
            if not success:
                return False, f"Failed to grant points: {result}"  # 积分发放失败

            # 记录积分领取
            point_record = UserVideoPointRecord.query.filter_by(
                user_address=user_address,
                video_id=video_id
            ).first()
            if not point_record:
                point_record = UserVideoPointRecord(
                    user_address=user_address,
                    video_id=video_id,
                    point_amount=video.point_reward,
                    is_received=True,
                    receive_time=datetime.now(timezone.utc)
                )
                db.session.add(point_record)
            else:
                point_record.is_received = True
                point_record.point_amount = video.point_reward
                point_record.receive_time = datetime.now(timezone.utc)

            db.session.commit()
            return True, f"Successfully granted {video.point_reward} points"  # 成功发放N积分
        except Exception as e:
            db.session.rollback()
            return False, f"Grant failed: {str(e)}"  # 发放失败

    # Note: report_watch_progress method is deprecated, replaced by /video/report-progress-and-unlock API in main.py
    # 注意：report_watch_progress 方法已废弃，由 main.py 中的 /video/report-progress-and-unlock API 替代
    # New logic uses first/final timestamp diff validation (80%-500% duration range), not real-time progress reporting
    # 新逻辑使用首次/最终时间戳差值校验（80%-500%时长区间），而非实时进度上报