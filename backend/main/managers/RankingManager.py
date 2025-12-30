import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from sqlalchemy import func, distinct
from main.models.database import db
from main.models.SignInRecord import SignInRecord
from main.models.AnswerChallengeRecord import AnswerChallengeRecord

class RankingManager:
    _instance = None

    @classmethod
    def instance(cls):
        """单例模式，避免重复初始化"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_sign_in_ranking(self, limit=10):
        """获取签到累计积分前十名：用户地址 + 累计签到积分 + 签到天数"""
        # 按用户地址分组，求和签到奖励积分 + 统计签到天数（按日期去重）
        ranking_data = db.session.query(
            SignInRecord.user_address,
            func.sum(SignInRecord.reward_points).label('total_sign_in_points'),
            func.count(distinct(SignInRecord.sign_in_date)).label('sign_in_days')  # 签到天数
        ).group_by(SignInRecord.user_address).order_by(
            func.sum(SignInRecord.reward_points).desc()
        ).limit(limit).all()

        # 格式化返回数据
        return [
            {
                "user_address": item.user_address,
                "total_sign_in_points": item.total_sign_in_points or 0,
                "sign_in_days": item.sign_in_days or 0
            }
            for item in ranking_data
        ]

    def get_answer_ranking(self, limit=10):
        """获取答题累计积分前十名：用户地址 + 累计答题积分 + 答题总数 + 答题次数 + 总答对数"""
        # 按用户地址分组，补充答题总数（每次10题×挑战次数）、答题次数、总答对数
        ranking_data = db.session.query(
            AnswerChallengeRecord.user_address,
            func.sum(AnswerChallengeRecord.reward_points).label('total_answer_points'),  # 累计答题积分
            func.count(AnswerChallengeRecord.id).label('total_challenge_times'),         # 答题次数（挑战次数）
            func.sum(AnswerChallengeRecord.correct_count).label('total_correct_count'),  # 总答对数
            # 修正：先括号包裹乘法运算，再添加 label（SQLAlchemy 正确语法）
            (func.count(AnswerChallengeRecord.id) * 10).label('total_answer_questions')    # 答题总数（每次10题）
        ).group_by(AnswerChallengeRecord.user_address).order_by(
            func.sum(AnswerChallengeRecord.reward_points).desc()
        ).limit(limit).all()

        # 格式化返回数据（新增答题总数、答题次数、总答对数）
        return [
            {
                "user_address": item.user_address,
                "total_answer_points": item.total_answer_points or 0,
                "total_answer_questions": item.total_answer_questions or 0,  # 答题总数
                "total_challenge_times": item.total_challenge_times or 0,    # 答题次数
                "total_correct_count": item.total_correct_count or 0         # 总答对数
            }
            for item in ranking_data
        ]