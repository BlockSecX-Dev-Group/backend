# -*- coding: utf-8 -*-
"""
@author yumu
@version 1.0.0
"""
import os
import sys
from datetime import datetime

from main.models.ErrorLog import ErrorLog

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.models.database import *


class CustomException(Exception):
    """
    自定义的异常类的基类
    """

    def __init__(self, message):
        self.message = message
        self.record_error()

    def record_error(self):
        """
        触发异常自动记录到数据库中
        :return:
        """
        try:
            from flask import has_app_context
            if has_app_context():
                error = ErrorLog(error_event=self.message)
                db.session.add(error)
                db.session.commit()
            else:
                # 没有应用上下文时只打印错误
                print(f"[CustomException] {self.message}")
        except Exception as e:
            print(f"[CustomException] {self.message} (无法记录到数据库: {e})")


class ConfigOperationException(CustomException):
    """
    配置文件操作异常类
    """
    pass


class DatabaseOperationException(CustomException):
    """
    数据库操作异常类
    """
    pass


class DecoratorException(CustomException):
    """
    装饰器处理异常类
    """
    pass


class RewardException(CustomException):
    """
    奖励异常类
    """

class FieldException(CustomException):
    """
    靶场异常类
    """

class DecoratorException(CustomException):
    """
    装饰器处理异常类
    """
    pass

