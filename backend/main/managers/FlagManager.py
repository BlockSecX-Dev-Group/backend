
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from main.models.TargetFieldOpenRecord import *
from main.models.LevelPassRecord import *

class FlagManager:
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def check_flag(cls, field_id, flag, user_address):
        # 查询靶场运行记录
        field = TargetFieldOpenRecord.query.filter_by(field_id=field_id).first()
        if not field:
            return False, "Field not found!"

        # 验证是否是靶场所有者
        if field.user_address != user_address:
            return False, "You are not the owner of this field!"

        # 检查是否已通关
        pass_record = LevelPassRecord.query.filter_by(field_id=field_id).first()
        if pass_record:
            return False, "This level has already been passed!"

        # 验证Flag
        if field.flag == flag:
            new_record = LevelPassRecord(field_id=field_id, user_address=user_address)
            db.session.add(new_record)
            db.session.commit()
            return True, "Correct flag!"
        else:
            return False, "Incorrect flag!"
