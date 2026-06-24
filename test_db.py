import sys
from sqlalchemy.orm import configure_mappers
from sqlalchemy.orm.util import class_mapper

def test_orm_mapping():
    print("캠퍼스 민원 분석 플랫폼 ORM 설계 정적 매핑 검증을 시작합니다...")
    try:
        # configure_mappers()는 모델 간 관계 정의, 외래 키 바인딩 에러 등을 DB 접속 없이 분석하고 검증합니다.
        configure_mappers()
        print("✅ SQLAlchemy ORM 모델 구성에 성공했습니다! (모든 필드 및 관계성 정의 정상)")
        
        # 정의된 모델들
        from models import User, Complaint, Category, Department, ComplaintAttachment, AdminAction, Feedback, Report
        models = [User, Complaint, Category, Department, ComplaintAttachment, AdminAction, Feedback, Report]
        
        print("\n--- 테이블 매핑 상세 정보 ---")
        for model in models:
            mapper = class_mapper(model)
            columns = [col.name for col in mapper.columns]
            relationships = [rel.key for rel in mapper.relationships]
            
            print(f"[{model.__name__}] 테이블: '{mapper.local_table.name}'")
            print(f"  - 컬럼 목록: {', '.join(columns)}")
            if relationships:
                print(f"  - 관계 목록: {', '.join(relationships)}")
            print("-" * 30)
            
        print("\n🎉 DB 설계 및 ORM 구현이 논리적 오류 없이 구성되었습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ ORM 매핑 검증 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    test_orm_mapping()
