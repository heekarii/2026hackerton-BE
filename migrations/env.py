import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, text
from alembic import context

# 현재 프로젝트 디렉토리를 Python Path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 프로젝트 database 및 models 임포트
from database import DATABASE_URL
from models import Base

# Alembic 설정 객체
config = context.config

# database.py의 DATABASE_URL을 동적으로 설정 (% 문자가 configparser에서 파싱 오류를 내지 않도록 %%로 이스케이프 처리)
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

# 로거 설정
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata 연동 (autogenerate 기능을 위해 중요)
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Offline 모드 마이그레이션"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Online 모드 마이그레이션"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # pgvector 확장을 데이터베이스에 활성화
        # (마이그레이션 시점에 Vector 타입 테이블 생성 전 확장이 존재해야 에러가 발생하지 않음)
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        connection.commit()

        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
