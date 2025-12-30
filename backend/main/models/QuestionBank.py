import json
from main.models.database import db
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class QuestionBank(db.Model):
    __tablename__ = 'question_bank'  
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='题目ID')
    question_bank_id = db.Column(db.String(50), nullable=False, comment='题库ID（分类）')
    question = db.Column(db.Text, nullable=False, comment='题目内容')
    options = db.Column(db.Text, nullable=False, comment='选项（JSON格式）')
    correct_answer = db.Column(db.String(255), nullable=False, comment='正确答案')

    __table_args__ = (
        db.Index('idx_question_bank_id', 'question_bank_id'),
    )

    def get_options(self):
        """解析选项JSON（代码层校验，替代数据库约束）"""
        try:
            options = json.loads(self.options) if self.options else {}
            if not isinstance(options, (dict, list)):
                return {}
            return options
        except json.JSONDecodeError as e:
            print(f"【题目选项JSON解析失败】题目ID：{self.id}，错误：{str(e)}")
            return {}
        except Exception as e:
            print(f"【题目选项解析异常】题目ID：{self.id}，错误：{str(e)}")
            return {}

    def to_challenge_dict(self):
      """转换为答题接口返回格式（新增question_bank_id字段）"""
      return {
         "question_id": self.id,
         "question": self.question,
          "options": self.get_options(),
          "question_bank_id": self.question_bank_id  
        }