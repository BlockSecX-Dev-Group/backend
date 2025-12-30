# -*- coding: utf-8 -*-
"""
@author yumu
@version 1.0.0
"""
from flask_sqlalchemy import SQLAlchemy

"""
本项目使用的是flask_sqlalchemy，为了保证在整个flask上下文环境中db唯一，特设此文件生成唯一db，在其他文件中要使用db时均从此文件导入，
在main文件中要对db进行初始化
"""
db = SQLAlchemy()
