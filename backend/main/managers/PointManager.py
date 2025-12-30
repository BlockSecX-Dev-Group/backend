import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from main.models.UserPoints import UserPoints
from main.models.PointQueryLog import PointQueryLog
from main.models.database import db


class PointManager:
    """
    纯积分管理器 - 与 Token 系统完全独立
    用于：签到奖励、答题消耗/奖励、视频观看奖励、靶场扣费/奖励
    """
    _instance = None

    @classmethod
    def instance(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_user_points(self, user_address, query_source="internal", client_ip=None, user_agent=None, audit=False):
        """
        获取用户当前积分
        :param user_address: 用户地址
        :param query_source: 查询来源 (api/sign_in/answer/internal等)
        :param client_ip: 客户端IP
        :param user_agent: 用户代理
        :param audit: 是否记录审计日志
        """
        user_point = UserPoints.query.filter_by(user_address=user_address).first()
        if not user_point:
            user_point = UserPoints(user_address=user_address, total_points=0)
            db.session.add(user_point)
            db.session.commit()

        current_points = user_point.total_points

        # 记录审计日志
        if audit:
            self._log_query(user_address, current_points, query_source, client_ip, user_agent)

        return current_points

    def _log_query(self, user_address, query_points, query_source, client_ip=None, user_agent=None):
        """记录积分查询审计日志"""
        try:
            log = PointQueryLog(
                user_address=user_address,
                query_points=query_points,
                query_source=query_source,
                client_ip=client_ip,
                user_agent=user_agent
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            print(f"积分查询审计日志记录失败: {str(e)}")
            db.session.rollback()

    def add_points(self, user_address, points):
        """增加用户积分"""
        if points <= 0:
            return False, "积分值必须大于0"

        user_point = UserPoints.query.filter_by(user_address=user_address).first()
        if not user_point:
            user_point = UserPoints(user_address=user_address, total_points=points)
            db.session.add(user_point)
        else:
            user_point.total_points += points

        db.session.commit()
        return True, user_point.total_points

    def deduct_points(self, user_address, points):
        """扣除用户积分"""
        if points <= 0:
            return False, "扣除积分必须大于0"

        user_point = UserPoints.query.filter_by(user_address=user_address).first()
        if not user_point:
            return False, "用户积分记录不存在（初始积分0）"

        if user_point.total_points < points:
            return False, f"积分不足（当前{user_point.total_points}，需扣除{points}）"

        user_point.total_points -= points
        db.session.commit()
        return True, user_point.total_points