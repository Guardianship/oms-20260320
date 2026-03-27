#!/usr/bin/env python3
"""
清理数据库中的服务器
"""
import sys
import os

# 添加后端路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.database import init_db, get_db, Server, SessionLocal

def main():
    print("=" * 50)
    print("清理数据库中的服务器")
    print("=" * 50)

    db = SessionLocal()
    try:
        servers = db.query(Server).all()
        if not servers:
            print("\n没有服务器需要清理")
            return

        print(f"\n当前共有 {len(servers)} 个服务器:\n")
        for i, s in enumerate(servers, 1):
            print(f"  {i}. ID: {s.id}, 名称: {s.name}, 主机: {s.host}")

        print("\n" + "=" * 50)
        confirm = input("\n确认删除所有服务器吗？(yes/no): ")

        if confirm.lower() in ['yes', 'y']:
            db.query(Server).delete()
            db.commit()
            print("\n✅ 已删除所有服务器")
        else:
            print("\n❌ 取消操作")

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
    input("\n按 Enter 退出...")
