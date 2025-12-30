
from main.models.database import db
from main.models.VideoInfo import VideoInfo
from main.models.VideoSequence import VideoSequence
from main.models.UserVideoUnlockRecord import UserVideoUnlockRecord
from datetime import datetime, timezone, timedelta
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))



class VideoUnlockManager:
    _instance = None
    DAILY_UNLOCK_LIMIT = 1  # 每天最多解锁视频数量

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_today_unlock_count(self, user_address):
        """Get user's unlock count for today / 获取用户今日已解锁视频数量"""
        try:
            # 获取今天的开始时间（UTC 00:00:00）
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # 查询今天解锁的视频数量（排除第一个视频，因为第一个是默认解锁的）
            count = UserVideoUnlockRecord.query.filter(
                UserVideoUnlockRecord.user_address == user_address,
                UserVideoUnlockRecord.is_unlocked == True,
                UserVideoUnlockRecord.unlock_time >= today_start,
                UserVideoUnlockRecord.sequence_num > 1  # 排除第一个视频
            ).count()

            return count
        except Exception as e:
            print(f"Failed to get today's unlock count: {str(e)}")  # 获取今日解锁数量失败
            return 0

    def check_daily_unlock_limit(self, user_address):
        """Check if user has reached daily unlock limit / 检查用户是否已达到每日解锁上限"""
        today_count = self.get_today_unlock_count(user_address)
        if today_count >= self.DAILY_UNLOCK_LIMIT:
            return False, f"Daily unlock limit reached ({self.DAILY_UNLOCK_LIMIT} times), please come back tomorrow"  # 今日解锁次数已达上限，请明天再来
        return True, f"You can unlock {self.DAILY_UNLOCK_LIMIT - today_count} more video(s) today"  # 今日还可解锁N个视频

    def get_all_video_names(self):
        """Get all video names (sorted) / 获取所有视频名称（按顺序）"""
        try:
            query = db.session.query(VideoInfo, VideoSequence.sequence_num).\
                join(VideoSequence, VideoInfo.video_id == VideoSequence.video_id).\
                filter(VideoInfo.is_active == True).\
                order_by(VideoSequence.sequence_num)

            video_list = []
            for video, seq_num in query.all():
                video_dict = video.to_dict()
                video_dict['sequence_num'] = seq_num
                video_list.append(video_dict)

            return True, video_list, "Retrieved successfully"  # 获取成功
        except Exception as e:
            return False, [], f"Failed to retrieve: {str(e)}"  # 获取失败

    def check_can_play(self, user_address, video_id, update_watch_time=False):
        """
        Check if user can play the specified video / 检查用户是否可播放指定视频
        :param update_watch_time: Whether to update last watch time (only True when actually playing) / 是否更新最后观看时间（仅在真正播放时传True）
        """
        try:
            # 获取视频的顺序号
            video_seq = VideoSequence.query.filter_by(video_id=video_id).first()

            # 如果是第一个视频，且用户没有任何解锁记录，则默认可播放
            if video_seq and video_seq.sequence_num == 1:
                has_any_unlock = UserVideoUnlockRecord.query.filter_by(
                    user_address=user_address
                ).first()
                if not has_any_unlock:
                    return True, "First video unlocked by default"  # 默认解锁第一个视频

            # 否则检查解锁记录
            record = UserVideoUnlockRecord.query.filter_by(
                user_address=user_address,
                video_id=video_id
            ).first()

            if not record:
                return False, "Video not unlocked"  # 视频未解锁

            if record.is_unlocked:
                # 仅在明确需要时更新观看时间（避免查询列表时触发更新）
                if update_watch_time:
                    record.last_watch_time = datetime.now(timezone.utc)
                    db.session.commit()
                return True, "Can play"  # 可播放
            else:
                return False, "Video not unlocked"  # 视频未解锁
        except Exception as e:
            return False, f"Validation failed: {str(e)}"  # 校验失败

    def get_unlocked_videos(self, user_address):
        """Get user's unlocked video list / 获取用户已解锁的视频列表"""
        try:
            records = UserVideoUnlockRecord.query.filter_by(
                user_address=user_address,
                is_unlocked=True
            ).join(VideoInfo, UserVideoUnlockRecord.video_id == VideoInfo.video_id).\
                join(VideoSequence, VideoInfo.video_id == VideoSequence.video_id).\
                order_by(VideoSequence.sequence_num).all()

            video_list = []
            for record in records:
                video = VideoInfo.query.filter_by(video_id=record.video_id).first()
                if video:
                    video_dict = video.to_dict()
                    video_dict['sequence_num'] = record.sequence_num
                    video_list.append(video_dict)

            return True, video_list, "Retrieved successfully"  # 获取成功
        except Exception as e:
            return False, [], f"Failed to retrieve: {str(e)}"  # 获取失败

    def check_can_unlock_next(self, user_address, skip_daily_limit=False):
        """
        Check if next video can be unlocked / 检查是否可解锁下一个视频
        :param skip_daily_limit: Whether to skip daily limit check (skip when auto-unlock) / 是否跳过每日限制检查（自动解锁时跳过）
        :return: (can_unlock: bool, message: str, next_video: VideoSequence or None)
        """
        try:
            # 获取用户已解锁的最大顺序号
            unlocked_records = UserVideoUnlockRecord.query.filter_by(
                user_address=user_address,
                is_unlocked=True
            ).all()

            if not unlocked_records:
                # 未解锁任何视频，检查第一个视频是否存在
                first_video = VideoSequence.query.order_by(VideoSequence.sequence_num).first()
                if not first_video:
                    return False, "No videos available", None  # 无可用视频
                # 第一个视频默认可播放，这里检查的是"解锁第二个"的前置条件
                return False, "Please watch the first video first", None  # 请先观看完成第一个视频

            max_seq = max([r.sequence_num for r in unlocked_records])
            # 检查下一个顺序号是否存在
            next_seq = max_seq + 1
            next_video = VideoSequence.query.filter_by(sequence_num=next_seq).first()

            if not next_video:
                return False, "All videos unlocked", None  # 已解锁所有视频

            # 检查上一个视频是否观看完成
            last_record = UserVideoUnlockRecord.query.filter_by(
                user_address=user_address,
                sequence_num=max_seq
            ).first()

            if not (last_record and last_record.is_watched):
                return False, "Previous video not completed, cannot unlock", None  # 上一个视频未观看完成，无法解锁

            # 检查每日解锁次数限制（自动解锁时可跳过）
            if not skip_daily_limit:
                can_unlock_today, limit_msg = self.check_daily_unlock_limit(user_address)
                if not can_unlock_today:
                    return False, limit_msg, None

            return True, "Can unlock next video", next_video  # 可解锁下一个视频
        except Exception as e:
            return False, f"Validation failed: {str(e)}", None  # 校验失败

    def unlock_next_video(self, user_address, auto_unlock=False):
        """
        Unlock next video / 解锁下一个视频
        :param auto_unlock: Whether auto-unlock (triggered after watching, NOT skip daily limit anymore) / 是否为自动解锁（看完视频后自动触发，不再跳过每日限制）
        """
        try:
            # 修改：auto_unlock 不再跳过每日限制，统一受限
            can_unlock, msg, next_video = self.check_can_unlock_next(user_address, skip_daily_limit=False)
            if not can_unlock:
                return False, msg

            next_seq = next_video.sequence_num

            # 创建/更新解锁记录
            record = UserVideoUnlockRecord.query.filter_by(
                user_address=user_address,
                video_id=next_video.video_id
            ).first()

            if not record:
                record = UserVideoUnlockRecord(
                    user_address=user_address,
                    video_id=next_video.video_id,
                    sequence_num=next_seq,
                    is_unlocked=True,
                    unlock_time=datetime.now(timezone.utc)
                )
                db.session.add(record)
            else:
                record.is_unlocked = True
                record.unlock_time = datetime.now(timezone.utc)

            # 注意：这里不 commit，由调用方统一 commit
            return True, f"Successfully unlocked video #{next_seq}"  # 成功解锁第N个视频
        except Exception as e:
            return False, f"Unlock failed: {str(e)}"  # 解锁失败

    def check_and_unlock_on_new_day(self, user_address):
        """
        跨日检查：如果用户前一天已看完当前最新解锁的视频，今天自动解锁下一个
        Check on new day: if user has watched the latest unlocked video, auto unlock next one today
        :return: (unlocked: bool, message: str)
        """
        try:
            # 获取用户已解锁的最大顺序号
            unlocked_records = UserVideoUnlockRecord.query.filter_by(
                user_address=user_address,
                is_unlocked=True
            ).all()

            if not unlocked_records:
                # 新用户，无需处理（第一个视频默认可播放）
                return False, "New user, first video available by default"

            # 找到最新解锁的视频记录
            max_seq = max([r.sequence_num for r in unlocked_records])
            latest_record = UserVideoUnlockRecord.query.filter_by(
                user_address=user_address,
                sequence_num=max_seq
            ).first()

            if not latest_record:
                return False, "Record not found"

            # 检查最新解锁的视频是否已观看完成
            if not latest_record.is_watched:
                return False, "Latest unlocked video not watched yet"

            # 检查今日是否已解锁过视频
            today_count = self.get_today_unlock_count(user_address)
            if today_count >= self.DAILY_UNLOCK_LIMIT:
                return False, f"Daily unlock limit reached ({self.DAILY_UNLOCK_LIMIT} video per day)"

            # 检查是否还有下一个视频可解锁
            next_seq = max_seq + 1
            next_video = VideoSequence.query.filter_by(sequence_num=next_seq).first()
            if not next_video:
                return False, "All videos unlocked"

            # 执行解锁
            record = UserVideoUnlockRecord.query.filter_by(
                user_address=user_address,
                video_id=next_video.video_id
            ).first()

            if not record:
                record = UserVideoUnlockRecord(
                    user_address=user_address,
                    video_id=next_video.video_id,
                    sequence_num=next_seq,
                    is_unlocked=True,
                    unlock_time=datetime.now(timezone.utc)
                )
                db.session.add(record)
            else:
                record.is_unlocked = True
                record.unlock_time = datetime.now(timezone.utc)

            db.session.commit()
            return True, f"New day auto unlock: video #{next_seq}"
        except Exception as e:
            db.session.rollback()
            return False, f"Check failed: {str(e)}"