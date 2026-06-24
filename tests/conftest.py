import os

# pytest 실행 시작 시 .env 또는 쉘 환경에 설정된 실서버 DATABASE_URL이 로드되어 
# 테스트 실행 도중 실서버 데이터를 오염시키거나 Unique 제약 조건 오류를 일으키는 것을 방지합니다.
# 
# [사용 방법]
# 1. 일반 테스트 (기본값): 그냥 'pytest'를 실행하면 안전하게 인메모리 SQLite에서 테스트가 수행됩니다.
# 2. 특정 외부/로컬 DB 테스트: 'TEST_DATABASE_URL=postgresql://... pytest'와 같이 실행하면 해당 DB를 타겟으로 동작합니다.
test_db_url = os.getenv("TEST_DATABASE_URL")
if test_db_url:
    os.environ["DATABASE_URL"] = test_db_url
else:
    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

# 테스트 시 JWT 비밀 키도 안전한 기본값으로 세팅합니다.
if "JWT_SECRET_KEY" not in os.environ:
    os.environ["JWT_SECRET_KEY"] = "test-secret-key"

