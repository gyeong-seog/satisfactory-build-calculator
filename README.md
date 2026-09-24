# 세티스팩토리 빌드 계산기

Satisfactory의 생산 목표부터 원자재까지 공정을 계산하고 시각화하는 Windows용 비공식 커뮤니티 도구입니다.

> **비공식 프로젝트 안내**
>
> 이 프로젝트는 Coffee Stain Studios와 제휴하거나 승인받은 공식 제품이 아닙니다.
> Satisfactory 및 관련 명칭과 데이터의 권리는 각 권리자에게 있습니다.

## 주요 기능

- 제품 목표 생산량에서 원자재까지 생산 트리 자동 계산
- 기본·대체 레시피 선택 및 즉시 재계산
- 생산시설별 필요/설치 대수, 동력핵, 소머슬롭, 소비 전력 계산
- 바이오매스·석탄·연료·원자력·지열 발전기와 외계 전력 증폭기 계산
- 고체 `개/min`, 액체·가스 `m³/min`, 전력 `MW` 단위 자동 표시
- 완료한 상위 공정의 하위 공정 숨김 및 완료 취소
- 카드 자유 배치, 배치 고정, 초기화, 전체 보기와 화면 이동
- 생산시설별 색상 및 시설명 표시
- 한국어/영어 전환
- 창 닫기 시 시스템 트레이 대기
- 사용자가 지정하는 Windows 전역 표시/숨김 단축키

## 다운로드

일반 사용자는 GitHub의 **Releases**에서 최신 `SatisfactoryBuildCalculator.exe`를 받으면 됩니다. Python이나 별도 데이터 파일은 필요하지 않습니다.

현재 공개 초기 버전은 코드 서명이 없으므로 Windows SmartScreen이 `알 수 없는 게시자` 경고를 표시할 수 있습니다. 다운로드한 파일의 SHA-256을 Release에 첨부된 `SHA256SUMS.txt`와 비교할 수 있습니다.

이 프로젝트는 향후 Windows Release 서명에 SignPath Foundation의 무료 오픈소스 코드 서명 서비스를 사용하기 위해 신청 중입니다. 승인 이후의 서명된 버전은 Release 설명에 명확히 표시하며, 현재 `v0.1.0`은 서명되지 않은 초기 버전입니다. 자세한 운영 원칙은 [Code signing policy](CODE_SIGNING_POLICY.md)를 확인하세요.

```powershell
Get-FileHash .\SatisfactoryBuildCalculator.exe -Algorithm SHA256
```

## 소스에서 실행

요구 사항: Windows 10/11, Python 3.12

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py
```

기본 표시/숨김 단축키는 `Ctrl+Shift+S`이며 프로그램의 `단축키 설정`에서 변경할 수 있습니다.

## 테스트

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
```

## 단일 EXE 빌드

```powershell
.\.venv\Scripts\python -m pip install pyinstaller==6.22.3
.\.venv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --windowed `
  --name SatisfactoryBuildCalculator --version-file version_info.txt `
  --add-data "data;data" main.py
```

Git 태그 `v*`를 푸시하면 GitHub Actions가 Windows 환경에서 테스트하고 EXE·체크섬·빌드 출처 증명을 포함한 Release를 자동 생성합니다.

## 개인정보와 네트워크

- 게임 프로세스나 저장 파일을 읽거나 수정하지 않습니다.
- 인터넷 연결, 사용자 계정, 광고, 분석 정보 수집 기능이 없습니다.
- 사용자 설정은 Windows의 Qt 설정 저장소에 로컬로만 저장됩니다.

자세한 내용은 [개인정보 처리방침](PRIVACY.md)을 확인하세요.

## 데이터

실행에 필요한 가공 데이터는 `data/items.json`, `data/recipes.json`, `data/buildings.json`에 있습니다. 배포 저장소에는 게임에서 추출한 원본 언어 파일을 포함하지 않습니다. 출처와 적용 범위는 [DATA_NOTICE.md](DATA_NOTICE.md)를 확인하세요.

## 라이선스

프로그램 소스 코드는 [MIT License](LICENSE)로 공개됩니다. 게임 관련 명칭·데이터와 제3자 구성요소는 MIT License의 적용 대상이 아닙니다. PySide6, Qt, PyInstaller 등 제3자 구성요소의 조건은 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)를 확인하세요.

문제나 잘못된 계산을 발견하면 재현 방법, 선택한 제품·레시피·목표량을 GitHub Issue에 남겨주세요.
