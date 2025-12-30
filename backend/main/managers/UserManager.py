
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.models.UserData import *
from main.models.LevelPassRecord import *
from main.models.TargetFieldOpenRecord import *
from main.models.Field import *

class UserManager:

    @classmethod
    def get_user_balance(cls, user_address):
        user = UserData.query.filter_by(user_address=user_address).first()
        if user:
            return user.token_balance
        else:
            new_user = UserData(
                user_address=user_address,
                token_balance=0
            )
            db.session.add(new_user)  # 将新用户添加到 session
            db.session.commit()
            return 0

    @classmethod
    def update_user_balance(cls, user_address, user_balance_change):
        user = UserData.query.filter_by(user_address=user_address).first()
        if user:
            if user_balance_change >= 0:
                user.token_balance += user_balance_change
                db.session.commit()
                return True
            elif user_balance_change < 0:
                if user.token_balance + user_balance_change < 0:
                    return False
                else:
                    user.token_balance += user_balance_change
                    db.session.commit()
                    return True
        else:
            new_user = UserData(
                user_address=user_address,
                token_balance=0
            )
            db.session.add(new_user)  # 将新用户添加到 session
            if user_balance_change >= 0:
                new_user.token_balance += user_balance_change
                db.session.commit()
                return True
            elif user_balance_change < 0:
                db.session.commit()
                return False
            return 0

    @classmethod
    def get_available_fields_for_user(cls, user_address):
        # 检查用户当前是否有运行中的靶场
        running_fields = TargetFieldOpenRecord.query.filter_by(
            user_address=user_address,
            status='running'
        ).count()
        if running_fields > 0:
            return False, [], "User has a running field"  # 如果有运行中的靶场，返回空列表

        # 获取用户的所有通关记录
        passed_records = LevelPassRecord.query.filter_by(user_address=user_address).all()
        if not passed_records:
            # 如果用户没有通关记录，返回第一个靶场
            first_field = Field.query.order_by(Field.id.asc()).first()
            return True, [first_field.field_name] if first_field else [], "Success to get available fields for user."

        # 通过容器 ID 获取通关的靶场名称
        passed_field_names = set()
        for record in passed_records:
            open_record = TargetFieldOpenRecord.query.filter_by(field_id=record.field_id).first()
            if open_record and open_record.field_name:
                passed_field_names.add(open_record.field_name)

        # 从 Field 表获取所有靶场，按 id 排序
        all_fields = Field.query.order_by(Field.id.asc()).all()
        if not all_fields:
            return True, [], "Field list is empty."  # 如果 Field 表为空，返回空列表

        # ----------下面是自定义判断用户是否能解锁靶场的逻辑，目前按照最基础的通关逻辑来实现，后面根据实际情况修改-------

        # 以总的靶场列表为基础来遍历，方便确定用户通关的最大连续 id
        max_passed_id = 0
        for field in all_fields:
            # 这样写是为了保证如果直接替换式更新靶场逻辑上也不会有问题
            if field.field_name not in passed_field_names:
                break  # 一旦发现未通关的靶场名称，停止计数
            max_passed_id = field.id

        # 获取所有解锁的靶场（id <= max_passed_id + 1）
        unlocked_fields = Field.query.filter(Field.id <= max_passed_id + 1).order_by(Field.id.asc()).all()

        # -----------------自定义核心判断逻辑代码到这里为止------------------

        # 返回所有解锁靶场的名字
        return True, [field.field_name for field in unlocked_fields], "Success to get available fields for user."

    @classmethod
    def get_running_field_for_user(cls, user_address):
        # 获取用户当前正在运行的靶场
        running_field = TargetFieldOpenRecord.query.filter_by(
            user_address=user_address,
            status='running'
        ).first()
        if running_field:
            host_port = getattr(running_field, 'host_port', None)
            return True, running_field.field_id, running_field.field_name, host_port, "User has a running field"
        else:
            return False, "", "", None, "User has no running field"
