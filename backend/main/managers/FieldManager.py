
import os
import sys
import docker
import string
import secrets
import time
import psutil
import iptc
from docker.errors import NotFound, APIError
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from main.models.TargetFieldOpenRecord import *
from main.models.Field import *
from main.managers.UserManager import *

class FieldManager:


    client = docker.from_env()

    def run_container(self, image_name, container_name, port_mapping=None):
        # 如果没有提供端口映射，使用默认
        if port_mapping:
            container = self.client.containers.run(image_name, name=container_name, detach=True, ports=port_mapping)
        else:
            container = self.client.containers.run(image_name, name=container_name, detach=True)
        return container

    def generate_flag(cls, prefix='flag', length=24):
        """
        生成形如 flag{随机字符串} 的唯一标识。
        :param prefix:  旗标前缀，默认 'flag'
        :param length:  随机字符串长度，默认 16
        :return:        完整的 flag，如 'flag{W8R7zCfQxv2LJ3AB}'
        """
        # 使用 string.ascii_letters + string.digits 作为字符集
        charset = string.ascii_letters + string.digits
        # 使用 secrets.choice 获取更安全的随机值
        random_str = ''.join(secrets.choice(charset) for _ in range(length))
        return f"{prefix}{{{random_str}}}"

    def allow_port_iptables(self, port):
        """
        在 INPUT 链上添加一条规则，允许对指定 TCP 端口的访问
        """
        table = iptc.Table(iptc.Table.FILTER)
        chain = iptc.Chain(table, "INPUT")

        rule = iptc.Rule()
        rule.protocol = "tcp"

        match = rule.create_match("tcp")
        match.dport = str(port)

        rule.target = iptc.Target(rule, "ACCEPT")
        chain.insert_rule(rule)

        # 如果需要立即生效，可以执行 table.commit()
        table.commit()

    def get_used_ports(self):
        used_ports = set()
        connections = psutil.net_connections(kind='inet')  # 获取 TCP/UDP 网络连接
        for conn in connections:
            # conn.laddr 形式为: addr(ip, port)
            if conn.laddr and conn.laddr.port:
                used_ports.add(conn.laddr.port)
            if conn.raddr and conn.raddr.port:
                used_ports.add(conn.raddr.port)
        return used_ports

    def find_free_ports(self, start=10000, end=65535, limit=10):
        """从指定范围内查找空闲端口，并返回前 limit 个"""
        used = self.get_used_ports()
        free_ports = []
        for port in range(start, end + 1):
            if port not in used:
                free_ports.append(port)
            if len(free_ports) == limit:
                break
        return free_ports

    def create_field(self, field_name, user_address):
        try:
            res, user_available_fields, msg = UserManager.get_available_fields_for_user(user_address)
            print(res, user_available_fields, msg)
            # TODO 做负载测试用的，后面要记得删掉
            # user_available_fields = ["c0ny1/upload-labs:latest"]
            # 用户没有权限开启当前指定的靶场
            if res and field_name not in user_available_fields:
                return False, "User does not have access to this field", "", 0
            # 用户已有正在运行的靶场
            elif not res and field_name not in user_available_fields:
                return False, "User has a running field", "", 0
            # 正常创建靶场
            else:
                # 从配置读取域名
                from main.managers.Config import Config
                base_url = Config.get_value("BASE_DOMAIN_NAME")

                # 加一个检查端口并且开防火墙的操作，对应还有销毁机制
                free_ports = self.find_free_ports()
                free_port = free_ports[0]

                # 实际上要把靶场名字替换为docker名字
                target_field = Field.query.filter_by(field_name=field_name).first()
                image_name = target_field.docker_name

                # 获取容器内部端口，默认80
                container_port = getattr(target_field, 'container_port', None) or 80
                port_mapping = {f"{container_port}/tcp": free_port}
                self.allow_port_iptables(free_port)
                # image_name = "c0ny1/upload-labs:latest"
                # 即取出upload-labs拼接时间戳作为容器名
                container_name = image_name.split(":")[0].split("/")[-1] + str(int(time.time()))
                container = self.run_container(image_name, container_name, port_mapping=port_mapping)

                flag = self.generate_flag()
                # 在容器内写入 flag 文件
                container.exec_run(f"bash -c 'echo {flag} > /root/flag.txt'")
                field_id = container.id

                # 创建靶场完成，记录到数据库（包含端口信息）
                new_field = TargetFieldOpenRecord(field_id=field_id, field_name=field_name, user_address=user_address, flag=flag, host_port=free_port, start_time=datetime.utcnow())
                db.session.add(new_field)
                db.session.commit()
                # 返回完整 URL 格式：http://域名:端口
                full_url = f"http://{base_url}:{free_port}"
                return True, field_id, full_url, free_port
        except Exception as e:
            print(e)
            return False, "Failed to create field", "", 0

    def shutdown_field(self, field_id):
        container_id = field_id
        try:
            # 获取容器对象
            container = self.client.containers.get(container_id)

            # 尝试正常停止容器（设置超时为 10 秒）
            print(f"尝试停止容器 {container_id}...")
            container.stop(timeout=10)  # 10 秒超时，超时后 Docker 会强制杀掉进程
            print(f"容器 {container_id} 已停止")

            # 删除容器
            container.remove()
            print(f"容器 {container_id} 已删除")
            return True

        except docker.errors.NotFound:
            print(f"未找到容器 {container_id}")
            return False

        except docker.errors.APIError as e:
            # 如果停止或删除失败（例如超时、权限问题），尝试强制删除
            print(f"正常停止或删除容器 {container_id} 失败: {e}")
            try:
                print(f"尝试强制删除容器 {container_id}...")
                container.remove(force=True)
                print(f"容器 {container_id} 已强制删除")
                return True
            except docker.errors.APIError as force_error:
                print(f"强制删除容器 {container_id} 失败: {force_error}")
                return False

        except Exception as e:
            # 捕获其他未预期的错误
            print(f"操作容器 {container_id} 时发生未知错误: {e}")
            return False

    def get_all_fields_info(self):
        all_fields = Field.query.all()
        all_fields_info = [{
            "field_name": field.field_name,
            "cost": field.cost,
            "description": field.description
        } for field in all_fields]
        return all_fields_info

    def get_field_cost_map(cls):
        all_fields = Field.query.all()
        field_cost_map = {}
        for field in all_fields:
            field_cost_map[field.field_name] = field.cost
        return field_cost_map
