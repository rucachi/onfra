# 카메라 추적 애플리케이션 (Camera Tracking Application)

PySide6 기반 실시간 객체 추적 데스크톱 애플리케이션입니다.

## 주요 기능

- **카메라 설정**: USB/산업용 카메라 연결 및 파라미터 조정 (해상도, FPS, 노출, 게인 등)
- **학습 모드**: ROI 선택 및 템플릿 등록 (ORB 특징점 기반)
- **관찰 모드**: 실시간 객체 추적 (ORB 매칭 + CSRT 트래커)
- **스케일 변화 대응**: 물체가 가까워지거나 멀어져도 추적 유지
- **자동 재탐색**: 추적 실패 시 자동으로 재탐색

## 설치 방법

### 1. Python 환경 준비
Python 3.8 이상이 필요합니다.

```bash
python --version
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 로고 파일 준비 (선택사항)

회사 로고 파일을 다음 경로에 배치하세요:
```
C:\onfra\onfra.png
```

로고 파일이 없어도 애플리케이션은 정상 실행됩니다.

## 실행 방법

```bash
cd C:\onfra
python main.py
```

## 사용 방법

### 1. Camera Settings (카메라 설정)
- 카메라 선택: 드롭다운에서 카메라 인덱스 선택
- 연결: "연결" 버튼 클릭
- 파라미터 조정: 해상도, FPS, 노출, 게인 등 조정
- 설정 저장: "설정 저장" 버튼으로 현재 설정 저장

### 2. Training (학습)
- 프리뷰 화면에서 마우스 드래그로 ROI 선택
- 템플릿 이름 입력 (예: "target_01")
- "학습" 버튼 클릭하여 템플릿 등록
- 품질 지표 확인 (키포인트 수, 매칭 점수)
- "저장" 버튼으로 레시피 저장

### 3. Observation (관찰)
- 레시피 선택
- "시작" 버튼으로 추적 시작
- 실시간 추적 상태 확인:
  - **SEARCH**: 객체 탐색 중
  - **TRACK**: 추적 중
  - **LOST**: 추적 실패
  - **REACQUIRE**: 재탐색 중
- "재탐색" 버튼으로 강제 재탐색

## 아키텍처

### 멀티스레드 구조
- **UI Thread**: 사용자 인터페이스 처리
- **Capture Thread**: 카메라 프레임 캡처
- **Vision Thread**: 영상 처리 및 추적

### 추적 알고리즘
1. **ORB 특징점 매칭**: 초기 객체 위치 탐지
2. **CSRT 트래커**: 실시간 빠른 추적
3. **상태 머신**: SEARCH → TRACK → LOST → REACQUIRE

### 파일 구조

```
C:\onfra\
├── main.py                    # 애플리케이션 진입점
├── assets.py                  # 로고 로딩
├── requirements.txt           # 의존성
├── README.md                  # 문서
├── ui/
│   ├── __init__.py
│   ├── main_window.py        # 메인 윈도우
│   ├── pages_camera.py       # 카메라 설정 페이지
│   ├── pages_training.py     # 학습 페이지
│   └── pages_observation.py  # 관찰 페이지
├── vision/
│   ├── __init__.py
│   ├── camera.py             # 카메라 캡처 스레드
│   ├── recipe.py             # 템플릿 관리
│   ├── tracker_pipeline.py   # 추적 파이프라인
│   └── utils.py              # 유틸리티
└── data/
    └── recipes/              # 저장된 템플릿
```

## 문제 해결

### 카메라가 연결되지 않을 때
- 카메라가 물리적으로 연결되어 있는지 확인
- 다른 프로그램에서 카메라를 사용 중인지 확인
- 카메라 인덱스를 변경해보세요 (0, 1, 2...)

### 추적이 잘 안 될 때
- ROI 선택 시 특징점이 많은 영역 선택
- 조명 조건 개선
- 카메라 노출/게인 조정
- 템플릿 재등록

### 로고가 표시되지 않을 때
- `C:\onfra\onfra.png` 경로에 파일이 있는지 확인
- 파일 권한 확인
- 상태바에 에러 메시지 확인

## 개발 정보

- **UI Framework**: PySide6 (Qt for Python)
- **Vision Library**: OpenCV
- **추적 알고리즘**: ORB + CSRT
- **데이터 형식**: JSON (메타데이터), PNG (이미지), NPY (디스크립터)

## 라이선스

(재)국제도시물정보과학연구원 (International Center for Urban Water Information Science)
