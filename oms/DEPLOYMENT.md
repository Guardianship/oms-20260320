# 运维管理系统 - 部署指南

## 方法一：快速打包（推荐）

在本机运行：
```
python package.py
```
这会生成一个 `oms_deploy_YYYYMMDD_HHMMSS.zip` 文件，把这个zip文件复制到目标机器即可。

---

## 方法二：手动复制

### 1. 复制文件
把整个 `oms` 文件夹复制到U盘或网盘，然后复制到目标机器。

**可以删除的文件夹（节省空间）：**
- `backend/venv/` （虚拟环境，目标机器会自动重建）
- `data/oms.db` （数据库，新机器重新生成）

### 2. 目标机器环境准备

#### 安装 Python
1. 访问 https://www.python.org/downloads/
2. 下载 Python 3.8 或更高版本（推荐 3.10/3.11）
3. 运行安装程序，**重要：勾选 "Add Python to PATH"**

#### 验证 Python
打开CMD，输入：
```
python --version
```
如果显示版本号，说明安装成功。

### 3. 启动系统
1. 进入 oms 文件夹
2. 双击 `run.bat`
3. 等待依赖安装完成（首次启动较慢）
4. 打开浏览器访问 http://localhost:8000

---

## 常见问题

### Q: 提示找不到 python？
A: 重新安装Python，确保勾选 "Add Python to PATH"

### Q: 模块安装失败？
A: 检查网络连接，或尝试手动安装：
```
cd backend
pip install -r requirements.txt
```

### Q: 如何让其他电脑也能访问这个系统？
A: 修改启动地址为 0.0.0.0（已默认设置），然后防火墙开放8000端口，其他电脑通过 `http://你的IP:8000` 访问

---

## 目录结构

```
oms/
├── backend/          # 后端程序
├── frontend/         # 前端页面
├── data/             # 数据库（自动生成）
├── start.py          # Python启动脚本
├── run.bat           # Windows启动脚本
├── package.py        # 打包脚本
└── README.txt        # 使用说明
```
