"""
监控功能模块 - 本机Windows和远程Linux
"""
import time
import paramiko
import psutil


def get_local_metrics():
    """获取本机Windows监控数据"""
    try:
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)

        # 内存
        mem = psutil.virtual_memory()
        memory_percent = mem.percent
        memory_total = round(mem.total / (1024**3), 2)
        memory_used = round(mem.used / (1024**3), 2)

        # 磁盘 (取系统盘)
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_total = round(disk.total / (1024**3), 2)
        disk_used = round(disk.used / (1024**3), 2)

        return {
            "success": True,
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "disk_percent": disk_percent,
            "memory_total": memory_total,
            "memory_used": memory_used,
            "disk_total": disk_total,
            "disk_used": disk_used
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def get_linux_metrics(host, port, username, password):
    """通过SSH获取Linux服务器监控数据"""
    client = None
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=username, password=password, timeout=10)

        # 获取CPU使用率
        stdin, stdout, stderr = client.exec_command("top -bn1 | grep 'Cpu(s)' | sed 's/.*, *\\([0-9.]*\\)%* id.*/\\1/' | awk '{print 100 - $1}'")
        cpu_output = stdout.read().decode().strip()
        cpu_percent = float(cpu_output) if cpu_output else 0

        # 获取内存使用率
        stdin, stdout, stderr = client.exec_command("free -m")
        mem_output = stdout.read().decode()
        mem_lines = mem_output.split('\n')
        memory_percent = 0
        memory_total = 0
        memory_used = 0
        if len(mem_lines) > 1:
            mem_info = mem_lines[1].split()
            if len(mem_info) >= 3:
                memory_total = int(mem_info[1]) / 1024  # MB -> GB
                memory_used = int(mem_info[2]) / 1024
                if memory_total > 0:
                    memory_percent = round((memory_used / memory_total) * 100, 2)
                memory_total = round(memory_total, 2)
                memory_used = round(memory_used, 2)

        # 获取磁盘使用率
        stdin, stdout, stderr = client.exec_command("df -P / | tail -1")
        disk_output = stdout.read().decode().strip()
        disk_percent = 0
        disk_total = 0
        disk_used = 0
        if disk_output:
            disk_info = disk_output.split()
            if len(disk_info) >= 5:
                disk_percent = float(disk_info[4].replace('%', ''))
                disk_total = round(int(disk_info[1]) / (1024**2), 2)  # KB -> GB
                disk_used = round(int(disk_info[2]) / (1024**2), 2)

        client.close()

        return {
            "success": True,
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "disk_percent": disk_percent,
            "memory_total": memory_total,
            "memory_used": memory_used,
            "disk_total": disk_total,
            "disk_used": disk_used
        }
    except Exception as e:
        if client:
            client.close()
        return {
            "success": False,
            "error": str(e)
        }
