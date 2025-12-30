from datetime import datetime, timezone
from sqlalchemy import func, distinct
from main.models.SignInRecord import SignInRecord
from main.managers.PointManager import PointManager
from main.models.database import db
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class SignInManager:
    _instance = None
    SIGN_REWARD = 10  # 每日签到奖励10积分

    @classmethod
    def instance(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def daily_sign_in(self, user_address):
        """每日签到：防重复+加积分（适配 MariaDB 生成列）"""
        # 基于 UTC 时间获取今日日期（与数据库生成列的时区一致）
        today_utc = datetime.now(timezone.utc).date()
        
        # 检查今日是否已签到（查询数据库自动生成的 sign_in_date）
        has_signed = SignInRecord.query.filter(
            SignInRecord.user_address == user_address,
            SignInRecord.sign_in_date == today_utc
        ).first()
        
        if has_signed:
            current_points = PointManager.instance().get_user_points(user_address)
            return False, "今日已签到，无法重复签到", current_points

        try:
            # 新增签到记录：仅传递非生成列（sign_in_date 由 MariaDB 自动生成）
            sign_record = SignInRecord(
                user_address=user_address,
                reward_points=self.SIGN_REWARD,
                sign_in_time=datetime.now(timezone.utc)
                # 绝对不要赋值 sign_in_date！数据库会自动计算
            )
            db.session.add(sign_record)
            
            # 增加积分
            success, result = PointManager.instance().add_points(user_address, self.SIGN_REWARD)
            if not success:
                db.session.rollback()
                return False, str(result), 0
            
            db.session.commit()
            current_points = PointManager.instance().get_user_points(user_address)
            return True, f"签到成功，获得{self.SIGN_REWARD}积分", current_points
        
        except Exception as e:
            db.session.rollback()
            error_msg = f"签到失败：{str(e)}"
            # 针对 MariaDB 1906 错误的特殊提示（兜底）
            if "1906" in str(e) or "generated column" in str(e).lower():
                error_msg = "签到失败：数据库生成列配置异常，请确认 sign_in_date 为自动生成列"
            print(f"【MariaDB 签到错误】{error_msg}")
            return False, error_msg, 0

    def get_user_sign_in_days(self, user_address):
        """获取用户累计签到天数"""
        result = db.session.query(
            func.count(distinct(SignInRecord.sign_in_date))
        ).filter(
            SignInRecord.user_address == user_address
        ).scalar()
        return result or 0