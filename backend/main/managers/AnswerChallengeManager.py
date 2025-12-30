from sqlalchemy import func
from main.models.QuestionBank import QuestionBank
from main.models.AnswerChallengeRecord import AnswerChallengeRecord
from main.models.AnswerSession import AnswerSession
from main.managers.PointManager import PointManager
from main.models.database import db
import os
import sys
import uuid
import json
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class AnswerChallengeManager:
    _instance = None
    CHALLENGE_COST = 10       # 答题消耗10积分（获取题目时扣除）
    QUESTION_NUM = 10         # 每次抽10题
    PER_CORRECT_POINT = 1     # 每题答对奖励1积分
    FULL_CORRECT_EXTRA = 5    # 全对额外奖励5积分
    ANSWER_TIMEOUT = 20       # 答题时效：20分钟

    @classmethod
    def instance(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_random_questions(self, user_address):
        """从ID 1-600中随机抽取10道题 + 生成带时效的答题会话"""
        # 1. 先扣除答题消耗的积分
        deduct_success, deduct_msg = PointManager.instance().deduct_points(user_address, self.CHALLENGE_COST)
        if not deduct_success:
            return False, "", f"获取题目失败：{str(deduct_msg)}"

        # 2. 筛选ID 1-600的题目 + 随机抽取10道
        query = QuestionBank.query.filter(QuestionBank.id.between(1, 600))
        total = query.count()
        if total < self.QUESTION_NUM:
            # 题目数量不足，回滚扣除的积分
            PointManager.instance().add_points(user_address, self.CHALLENGE_COST)
            return False, "", f"题目数量不足（当前仅{total}道，需至少{self.QUESTION_NUM}道），已返还10积分"
        
        # 3. 随机抽取10道题
        questions = query.order_by(func.rand()).limit(self.QUESTION_NUM).all()
        question_list = [q.to_challenge_dict() for q in questions]
        question_ids = [q.id for q in questions]

        # 4. 生成唯一答题会话ID + 20分钟过期时间
        session_id = str(uuid.uuid4())
        expire_at = datetime.now() + timedelta(minutes=self.ANSWER_TIMEOUT)
        # 保存会话（未提交、未过期）
        session = AnswerSession(
            session_id=session_id,
            user_address=user_address,
            question_ids=json.dumps(question_ids),
            is_submitted=False,
            is_expired=False,
            expire_at=expire_at
        )
        db.session.add(session)
        db.session.commit()

        # 返回：成功标识、会话ID、题目列表、过期时间（给前端展示）
        return True, session_id, {
            "questions": question_list,
            "expire_at": expire_at.strftime("%Y-%m-%d %H:%M:%S")  # 格式化过期时间
        }

    def submit_answers(self, user_address, session_id, user_answers):
        """提交答题结果（手动/自动）+ 多重校验（防重复、防过期）"""
        # 1. 基础校验：会话ID/答案格式
        if not session_id or not isinstance(session_id, str):
            return False, "参数错误：session_id不能为空", 0
        if not isinstance(user_answers, dict):
            user_answers = {}  # 自动提交时为空字典

        # 2. 查询会话 + 核心校验
        session = AnswerSession.query.filter_by(
            session_id=session_id,
            user_address=user_address
        ).first()
        if not session:
            return False, "答题会话不存在", 0
        if session.is_submitted:
            return False, "该会话已提交答案，无法重复提交", 0  # 防重复拿奖励
        if session.is_expired or session.is_session_expired():
            # 标记为过期，再提交（仅能提交一次）
            session.is_expired = True
            db.session.commit()
            return False, "答题会话已过期，无法提交", 0

        # 3. 校验题目ID匹配（手动提交时）
        question_ids = json.loads(session.question_ids)
        if len(user_answers) > 0:  # 手动提交才校验数量，自动提交（空答案）不校验
            if len(user_answers) != self.QUESTION_NUM:
                return False, f"需提交{self.QUESTION_NUM}道题答案", 0
            # 校验提交的题目ID是否和会话一致
            submit_question_ids = [int(q_id) for q_id in user_answers.keys()]
            if sorted(submit_question_ids) != sorted(question_ids):
                return False, "提交的题目ID与本次答题会话不匹配", 0

        # 4. 统计答对题数（自动提交时为0）
        correct_count = 0
        if len(user_answers) > 0:  # 手动提交才统计，自动提交无答案
            try:
                for q_id, user_ans in user_answers.items():
                    try:
                        question = QuestionBank.query.get(int(q_id))
                        if question and user_ans == question.correct_answer:
                            correct_count += 1
                    except:
                        continue
            except Exception as e:
                return False, f"答题统计失败：{str(e)}", 0

        # 5. 计算奖励积分（自动提交时为0）
        reward_points = 0
        if correct_count > 0:
            reward_points = correct_count * self.PER_CORRECT_POINT
            if correct_count == self.QUESTION_NUM:
                reward_points += self.FULL_CORRECT_EXTRA

        # 6. 发放奖励积分（有奖励才发）
        if reward_points > 0:
            add_success, add_msg = PointManager.instance().add_points(user_address, reward_points)
            if not add_success:
                return False, f"奖励发放失败：{str(add_msg)}", 0

        # 7. 标记会话为已提交（核心：防重复）
        try:
            # 记录答题日志
            record = AnswerChallengeRecord(
                user_address=user_address,
                cost_points=self.CHALLENGE_COST,
                correct_count=correct_count,
                reward_points=reward_points
            )
            db.session.add(record)
            # 更新会话状态
            session.is_submitted = True
            session.submitted_at = datetime.now()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return False, f"记录答题日志失败：{str(e)}", correct_count

        # 自动提交时的提示
        if len(user_answers) == 0:
            return True, "答题会话已过期，自动提交（无答案，无奖励）", 0
        return True, f"答题完成，共答对{correct_count}题，获得{reward_points}积分", correct_count