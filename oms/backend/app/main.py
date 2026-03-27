"""
运维管理系统 - 后端API主文件
"""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import JWTError, jwt
import hashlib
import hmac
import os
import csv
import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill

from app.database import (
    init_db, get_db, User, Server, Metric, cleanup_old_metrics
)
from app.monitor import get_local_metrics, get_linux_metrics

# 配置
SECRET_KEY = "oms-secret-key-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时
PASSWORD_SALT = "oms-salt-2024"

# 密码加密（使用简单的hash方案，避免bcrypt依赖问题）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")


def get_password_hash(password: str) -> str:
    """简单密码哈希"""
    return hashlib.sha256((password + PASSWORD_SALT).encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return hmac.compare_digest(
        get_password_hash(plain_password),
        hashed_password
    )

# 初始化
app = FastAPI(title="运维管理系统")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化数据库
init_db()

# 前端文件路径
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend")


# ========== Pydantic 模型 ==========

class UserCreate(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class ServerCreate(BaseModel):
    name: str
    host: str
    port: int = 22
    username: str
    password: str


class ServerUpdate(BaseModel):
    name: str
    host: str
    port: int
    username: str
    password: str


class ServerResponse(BaseModel):
    id: int
    name: str
    host: str
    port: int
    username: str
    created_at: datetime

    class Config:
        orm_mode = True


class MetricResponse(BaseModel):
    id: int
    server_id: int
    server_name: str
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    memory_total: float
    memory_used: float
    disk_total: float
    disk_used: float
    created_at: datetime

    class Config:
        orm_mode = True


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


# ========== 辅助函数 ==========

def create_default_user(db: Session):
    """创建/重置默认管理员用户"""
    user = db.query(User).filter(User.username == "admin").first()
    hashed_password = get_password_hash("admin123")
    if user:
        # 更新现有用户的密码
        user.password_hash = hashed_password
    else:
        # 创建新用户
        user = User(username="admin", password_hash=hashed_password)
        db.add(user)
    db.commit()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user


# 初始化默认用户
from sqlalchemy.orm import Session
from app.database import SessionLocal
db_tmp = SessionLocal()
try:
    create_default_user(db_tmp)
finally:
    db_tmp.close()


# ========== 前端页面路由 ==========

@app.get("/")
async def read_index():
    """首页"""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ========== API 路由 - 认证 ==========

@app.post("/api/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """登录获取token"""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/user/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user


@app.post("/api/user/change-password")
async def change_password(data: ChangePassword, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """修改密码"""
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    current_user.password_hash = get_password_hash(data.new_password)
    db.commit()
    return {"message": "密码修改成功"}


# ========== API 路由 - 服务器管理 ==========

@app.get("/api/servers", response_model=List[ServerResponse])
async def get_servers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取所有服务器列表"""
    servers = db.query(Server).all()
    return servers


@app.post("/api/servers", response_model=ServerResponse)
async def create_server(server: ServerCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """添加服务器"""
    db_server = Server(
        name=server.name,
        host=server.host,
        port=server.port,
        username=server.username,
        password=server.password
    )
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    return db_server


@app.put("/api/servers/{server_id}", response_model=ServerResponse)
async def update_server(server_id: int, server: ServerUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """更新服务器"""
    db_server = db.query(Server).filter(Server.id == server_id).first()
    if not db_server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    db_server.name = server.name
    db_server.host = server.host
    db_server.port = server.port
    db_server.username = server.username
    db_server.password = server.password
    db.commit()
    db.refresh(db_server)
    return db_server


@app.delete("/api/servers/{server_id}")
async def delete_server(server_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除服务器"""
    db_server = db.query(Server).filter(Server.id == server_id).first()
    if not db_server:
        raise HTTPException(status_code=404, detail="服务器不存在")
    db.delete(db_server)
    db.commit()
    # 同时删除该服务器的监控数据
    db.query(Metric).filter(Metric.server_id == server_id).delete()
    db.commit()
    return {"message": "删除成功"}


@app.post("/api/servers/import")
async def import_servers(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """批量导入服务器（CSV格式）"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="请上传CSV文件")

    content = await file.read()
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        text = content.decode('gbk')

    reader = csv.DictReader(io.StringIO(text))
    servers_to_import = []
    errors = []

    # 第一步：先验证所有数据
    for i, row in enumerate(reader, 2):
        try:
            name = row.get('name') or row.get('服务器名称')
            host = row.get('host') or row.get('主机地址')
            port_str = row.get('port') or row.get('端口') or '22'
            username = row.get('username') or row.get('用户名')
            password = row.get('password') or row.get('密码')

            if not all([name, host, username, password]):
                errors.append(f"第{i}行: 缺少必要字段（名称、主机、用户名、密码为必填）")
                continue

            port = int(port_str) if port_str else 22
            if port < 1 or port > 65535:
                errors.append(f"第{i}行: 端口号必须在1-65535之间")
                continue

            servers_to_import.append({
                "name": name.strip(),
                "host": host.strip(),
                "port": port,
                "username": username.strip(),
                "password": password.strip()
            })
        except ValueError:
            errors.append(f"第{i}行: 端口号格式错误")
        except Exception as e:
            errors.append(f"第{i}行: {str(e)}")

    # 如果有错误，直接返回，不导入
    if errors:
        raise HTTPException(status_code=400, detail={
            "message": "数据验证失败，请修正后重新导入",
            "errors": errors
        })

    # 第二步：验证通过，执行导入
    imported = 0
    for server_data in servers_to_import:
        db_server = Server(**server_data)
        db.add(db_server)
        imported += 1

    db.commit()
    return {
        "message": "导入成功",
        "imported": imported
    }


# ========== API 路由 - 监控数据 ==========

@app.get("/api/monitor/local")
async def monitor_local(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取本机监控数据并保存"""
    metrics = get_local_metrics()
    if metrics["success"]:
        # 保存到数据库
        db_metric = Metric(
            server_id=0,
            server_name="本机(Windows)",
            cpu_percent=metrics["cpu_percent"],
            memory_percent=metrics["memory_percent"],
            disk_percent=metrics["disk_percent"],
            memory_total=metrics["memory_total"],
            memory_used=metrics["memory_used"],
            disk_total=metrics["disk_total"],
            disk_used=metrics["disk_used"]
        )
        db.add(db_metric)
        # 清理旧数据
        cleanup_old_metrics(db)
        db.commit()
        db.refresh(db_metric)
        return {
            "success": True,
            "data": {
                "id": db_metric.id,
                "server_id": 0,
                "server_name": "本机(Windows)",
                **metrics
            }
        }
    return metrics


@app.get("/api/monitor/all")
async def monitor_all(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取所有服务器的监控数据"""
    results = []

    # 本机
    local_result = await monitor_local(db)
    if local_result.get("success"):
        results.append(local_result["data"])

    # 所有Linux服务器
    servers = db.query(Server).all()
    for server in servers:
        metrics = get_linux_metrics(
            server.host, server.port, server.username, server.password
        )
        if metrics["success"]:
            db_metric = Metric(
                server_id=server.id,
                server_name=server.name,
                cpu_percent=metrics["cpu_percent"],
                memory_percent=metrics["memory_percent"],
                disk_percent=metrics["disk_percent"],
                memory_total=metrics["memory_total"],
                memory_used=metrics["memory_used"],
                disk_total=metrics["disk_total"],
                disk_used=metrics["disk_used"]
            )
            db.add(db_metric)
            db.commit()
            db.refresh(db_metric)
            results.append({
                "id": db_metric.id,
                "server_id": server.id,
                "server_name": server.name,
                **metrics
            })
        else:
            results.append({
                "server_id": server.id,
                "server_name": server.name,
                "success": False,
                "error": metrics.get("error", "连接失败")
            })

    # 清理旧数据
    cleanup_old_metrics(db)
    return {"success": True, "data": results}


# ========== API 路由 - 历史数据和报表 ==========

@app.get("/api/metrics/{server_id}")
async def get_metrics(server_id: int, hours: int = 24, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取某服务器的历史监控数据"""
    cutoff = datetime.now() - timedelta(hours=hours)
    metrics = db.query(Metric).filter(
        Metric.server_id == server_id,
        Metric.created_at >= cutoff
    ).order_by(Metric.created_at.asc()).all()
    return {"success": True, "data": metrics}


@app.get("/api/metrics/history/{server_id}")
async def get_metrics_history(server_id: int, days: int = 7, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取历史数据用于图表"""
    cutoff = datetime.now() - timedelta(days=days)
    metrics = db.query(Metric).filter(
        Metric.server_id == server_id,
        Metric.created_at >= cutoff
    ).order_by(Metric.created_at.asc()).all()

    # 格式化数据给前端
    times = []
    cpu_data = []
    memory_data = []
    disk_data = []

    for m in metrics:
        times.append(m.created_at.strftime("%m-%d %H:%M"))
        cpu_data.append(m.cpu_percent)
        memory_data.append(m.memory_percent)
        disk_data.append(m.disk_percent)

    return {
        "success": True,
        "data": {
            "times": times,
            "cpu": cpu_data,
            "memory": memory_data,
            "disk": disk_data
        }
    }


def get_latest_metrics_data(db: Session):
    """获取所有服务器最新监控数据（内部函数）"""
    from sqlalchemy import desc

    servers = db.query(Server).all()
    results = []

    # 本机最新数据
    local_metric = db.query(Metric).filter(Metric.server_id == 0).order_by(desc(Metric.created_at)).first()
    if local_metric:
        results.append({
            "id": local_metric.id,
            "server_id": 0,
            "server_name": "本机(Windows)",
            "host": "127.0.0.1",
            "cpu_percent": local_metric.cpu_percent,
            "memory_percent": local_metric.memory_percent,
            "disk_percent": local_metric.disk_percent,
            "memory_total": local_metric.memory_total,
            "memory_used": local_metric.memory_used,
            "disk_total": local_metric.disk_total,
            "disk_used": local_metric.disk_used,
            "created_at": local_metric.created_at
        })

    # 各服务器最新数据
    for server in servers:
        metric = db.query(Metric).filter(Metric.server_id == server.id).order_by(desc(Metric.created_at)).first()
        if metric:
            results.append({
                "id": metric.id,
                "server_id": server.id,
                "server_name": server.name,
                "host": server.host,
                "cpu_percent": metric.cpu_percent,
                "memory_percent": metric.memory_percent,
                "disk_percent": metric.disk_percent,
                "memory_total": metric.memory_total,
                "memory_used": metric.memory_used,
                "disk_total": metric.disk_total,
                "disk_used": metric.disk_used,
                "created_at": metric.created_at
            })
        else:
            results.append({
                "id": None,
                "server_id": server.id,
                "server_name": server.name,
                "host": server.host,
                "cpu_percent": None,
                "memory_percent": None,
                "disk_percent": None,
                "memory_total": None,
                "memory_used": None,
                "disk_total": None,
                "disk_used": None,
                "created_at": None
            })

    return results


@app.get("/api/metrics/list/latest")
async def get_latest_metrics_list(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取所有服务器最新监控数据（列表形式）"""
    results = get_latest_metrics_data(db)
    return {"success": True, "data": results}


@app.get("/api/metrics/export/excel")
async def export_metrics_excel(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """导出监控数据为Excel"""
    from fastapi.responses import StreamingResponse

    try:
        wb = Workbook()
        ws = wb.active
        ws.title = "服务器监控数据"

        # 表头
        headers = ["服务器名称", "主机地址", "CPU使用率(%)", "内存使用率(%)", "磁盘使用率(%)",
                   "内存总量(GB)", "内存已用(GB)", "磁盘总量(GB)", "磁盘已用(GB)", "数据时间"]
        ws.append(headers)

        # 获取数据
        data_list = get_latest_metrics_data(db)
        for item in data_list:
            cpu_val = item["cpu_percent"] if item["cpu_percent"] is not None else "-"
            mem_val = item["memory_percent"] if item["memory_percent"] is not None else "-"
            disk_val = item["disk_percent"] if item["disk_percent"] is not None else "-"
            mem_total = item["memory_total"] if item["memory_total"] is not None else "-"
            mem_used = item["memory_used"] if item["memory_used"] is not None else "-"
            disk_total = item["disk_total"] if item["disk_total"] is not None else "-"
            disk_used = item["disk_used"] if item["disk_used"] is not None else "-"
            created_time = item["created_at"].strftime("%Y-%m-%d %H:%M:%S") if item["created_at"] else "-"

            row = [
                item["server_name"],
                item["host"],
                cpu_val,
                mem_val,
                disk_val,
                mem_total,
                mem_used,
                disk_total,
                disk_used,
                created_time
            ]
            ws.append(row)

        # 保存到内存
        excel_file = io.BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)

        filename = f"server_monitor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return StreamingResponse(
            excel_file,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        print(f"导出Excel错误: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
