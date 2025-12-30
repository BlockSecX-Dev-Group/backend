
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from main.models.database import db
from main.models.TargetFieldOpenRecord import TargetFieldOpenRecord
from main.models.LevelPassRecord import LevelPassRecord
from main.managers.FieldManager import FieldManager
from main.models.PaymentOrder import PaymentOrder
from main.managers.PaymentManager import PaymentManager
from main.managers.PointManager import PointManager

class DaemonTask:
    fieldManager = FieldManager()
    paymentManager = PaymentManager()
    @classmethod
    def get_single_field_total_rewards(cls):
        return {
            "field1": 1000,
            "field2": 2000,
            "field3": 3000,
        }

    @classmethod
    def distribute_rewards(cls, app):
        with app.app_context():  # 确保在 Flask 应用上下文中操作数据库
            # 获取当前 UTC 时间
            now = datetime.utcnow()
            # 计算 24 小时前的时间
            last_24h = now - timedelta(hours=24)

            # 查询过去 24 小时未分配奖励的通关记录
            # unrewarded_records是一个列表，里面包含了所有未分配奖励的通关记录，即LevelPassRecord
            unrewarded_records = LevelPassRecord.query.filter(
                LevelPassRecord.reward_amount.is_(None),
                LevelPassRecord.pass_time >= last_24h
            ).all()

            if not unrewarded_records:
                print("没有需要发放奖励的记录")
                return

            # 按 field_name 统计通关次数
            # 用这个字典来存，靶场名字对应通关次数
            field_pass_counts = {}
            for record in unrewarded_records:
                field = TargetFieldOpenRecord.query.filter_by(field_id=record.field_id).first()
                # 需要先检验是否存在
                if field and field.field_name:
                    field_name = field.field_name
                    field_pass_counts[field_name] = field_pass_counts.get(field_name, 0) + 1

            # 获取总奖励
            total_rewards = cls.get_single_field_total_rewards()

            # 计算并发放奖励
            # 选择对未分配奖励的通关记录进行遍历是为了算出奖励之后方便插入
            for record in unrewarded_records:
                field = TargetFieldOpenRecord.query.filter_by(field_id=record.field_id).first()
                # 这里要注意的就是可能通关记录里面有的靶场，但是在实际靶场信息或者靶场开放记录表里面没有，那么后续就不能执行，所以这里要先判断
                # 可能出现不一致情况的原因就是：
                # 1.靶场信息更新，直接把旧靶场删除了（这是不可取的）；
                # 2.为了优化关闭靶场时的耗时，对关闭的靶场记录直接做删除（这也是不可取的）
                if not field or not field.field_name:
                    continue

                field_name = field.field_name
                # 奖励列表要及时更新，更新的时候要考虑到还没有处理的靶场
                if field_name not in total_rewards:
                    continue  # 如果靶场不在奖励列表中，跳过

                # 计算单人奖励
                pass_count = field_pass_counts.get(field_name, 1)  # 至少为 1，避免除以 0
                reward_per_pass = total_rewards[field_name] / pass_count

                # 更新 LevelPassRecord 通关记录
                record.reward_amount = reward_per_pass
                db.session.add(record)

                # 使用 PointManager 发放积分奖励
                success, _ = PointManager.instance().add_points(record.user_address, int(reward_per_pass))
                if not success:
                    print(f"用户 {record.user_address} 积分发放失败")

            # 提交所有更改
            db.session.commit()
            print(f"{now}: 成功发放 {len(unrewarded_records)} 条记录的奖励")

    @classmethod
    def shutdown_field(cls, app):
        with app.app_context():
            now = datetime.utcnow()
            one_hour_ago = now - timedelta(hours=1)

            # 只查询运行中的靶场
            running_fields = TargetFieldOpenRecord.query.filter_by(status='running').all()

            for field in running_fields:
                field_id = field.field_id
                start_time = field.start_time

                # 条件 1：开启时间超过 1 小时
                if start_time <= one_hour_ago:
                    if cls.fieldManager.shutdown_field(field_id):
                        field.status = 'stop'
                        print(f"靶场 {field_id} 因超过 1 小时被关闭，状态更新为 stop")
                    else:
                        print(f"靶场 {field_id} 关闭失败，状态未更新")
                # 条件 2：未超时但已通关
                else:
                    passed = LevelPassRecord.query.filter_by(field_id=field_id).first()
                    if passed:
                        if cls.fieldManager.shutdown_field(field_id):
                            field.status = 'stop'
                            print(f"靶场 {field_id} 因已通关被关闭，状态更新为 stop")
                        else:
                            print(f"靶场 {field_id} 关闭失败，状态未更新")

            # 提交数据库更改
            db.session.commit()

    @classmethod
    def check_payment(cls, app):
        with app.app_context():
            unpaid_orders = PaymentOrder.query.filter_by(paid_status=False).all()
            for unpaid_order in unpaid_orders:
                # TODO 后面需要考虑接口请求速率限制，分批处理
                cls.paymentManager.check_payment(unpaid_order)

    @classmethod
    def start_daemon_task(cls, app):
        # 备选方案，一步开启，避免麻烦，但是需要修改时间尺度，因为不同
        cls.distribute_rewards(app)
        cls.shutdown_field(app)
