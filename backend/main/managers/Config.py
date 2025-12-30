# -*- coding: utf-8 -*-
"""
@author yumu
@version 1.0.0
"""
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(ROOT_DIR, "config.json")

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from main.models.typings import *


SCHEDULER_API_ENABLED = True  # 调试用，生产可设为False
SCHEDULER_TIMEZONE = "Asia/Shanghai"  # 时区，避免时间偏移


class Config:
    _instance = None

    @classmethod
    def _get_instance(cls, config_file=CONFIG_FILE):
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance.config_file = config_file
            cls._instance.config = cls._instance.load_config()
        return cls._instance

    @classmethod
    def load_config(cls):
        """
        加载配置文件
        :return: 配置文件，json形式
        """
        try:
            instance = cls._get_instance()
            if os.path.exists(instance.config_file):
                with open(instance.config_file, 'r', encoding='utf-8') as file:
                    return json.load(file)
            else:
                return {}
        except Exception as e:
            ConfigOperationException("读取配置文件出错" + ", ".join(str(arg) for arg in e.args))

    @classmethod
    def save_config(cls):
        """
        存入配置文件
        :return: None
        """
        try:
            instance = cls._get_instance()
            with open(instance.config_file, 'w') as file:
                json.dump(instance.config, file, indent=2)
        except Exception as e:
            ConfigOperationException("存入配置文件出错" + ", ".join(str(arg) for arg in e.args))

    @classmethod
    def get_value(cls, *args):
        """
        从配置文件中获取配置，针对多级key做了优化
        :param args: 指定的key，可以为多级
        :return: 获取到的值
        """
        instance = cls._get_instance()
        try:
            value = instance.config
            for key in args:
                value = value[key]
            return value
        except Exception as e:
            ConfigOperationException("从配置文件中获取配置出错" + ", ".join(str(arg) for arg in e.args))
            return None

    @classmethod
    def set_value(cls, *args):
        """
        修改配置文件的值，针对多级key做了优化
        :param args: 指定的key，可以为多级，最后一个参数是要修改的值
        :return: None
        """
        try:
            instance = cls._get_instance()
            value = args[-1]
            keys = args[:-1]

            config_section = instance.config
            for key in keys[:-1]:
                if key not in config_section:
                    config_section[key] = {}
                config_section = config_section[key]

            config_section[keys[-1]] = value
            cls.save_config()
        except Exception as e:
            ConfigOperationException("修改配置文件的值出错" + ", ".join(str(arg) for arg in e.args))
