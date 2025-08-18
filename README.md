# Mission Python - Code Restore Utility 🦊

![alt text](https://img.shields.io/badge/python-3.x-blue.svg)
![alt text](https://img.shields.io/badge/managed%20with-Poetry-blueviolet.svg)
![alt text](https://img.shields.io/badge/dependencies-standard%20library-green.svg)
![alt text](https://img.shields.io/badge/license-MIT-blue.svg)

**`mission-python` 프레임워크에서 생성된 로그 파일로부터 최종 버전의 소스 코드를 완벽하게 복원하는 공식 커맨드 라인 유틸리티입니다.**<br>
*The official command-line utility for completely restoring the final version of source code from the `mission-python` framework.*

---

## 🚀 프로젝트 개요 (Overview)

`mission-python` 프로젝트에서는 코드의 작성 과정을 단계별로 기록하기 위해, 초기 버전의 코드와 이후 모든 변경 사항(diff)을 단일 로그 파일에 순차적으로 저장합니다. 이 로그 파일은 코드의 전체 진화 과정을 담고 있는 귀중한 데이터입니다.

본 `mission-restore` 유틸리티는 이 로그 파일을 분석하여, 초기 코드에 기록된 모든 diff 패치를 순서대로 적용함으로써 최종 버전의 소스 코드를 완벽하게 재구성하는 역할을 수행합니다.

## ✨ 주요 기능 (Key Features)

-   **정확한 복원**: 초기 코드를 기준으로 모든 diff 패치를 순서대로 적용하여 최종 소스 코드를 100% 재현합니다.
-   **견고한 검증 로직**: 각 diff의 컨텍스트(Context) 라인을 원본 코드와 비교 검증하여, 패치가 정확한 위치에 적용되는지 확인하고 오류를 방지합니다.
-   **명확한 CLI 인터페이스**: `argparse`를 활용하여 직관적인 명령줄 인터페이스를 제공하며, 복원 과정의 각 단계를 명확하게 보여줍니다.
-   **경량 및 무의존성**: 복원 핵심 로직은 Python 표준 라이브러리만으로 구현되어 있어 가볍고, 추가 라이브러리 설치 없이 바로 사용할 수 있습니다.

## 🛠️ 시작하기 (Getting Started)

### 사전 요구사항 (Prerequisites)

-   [Python](https://www.python.org/downloads/) (3.10 이상 권장)
-   [Poetry](https://python-poetry.org/docs/#installation) (패키지 및 의존성 관리 도구)
-   Git

### 설치 및 설정 (Installation)

1.  **프로젝트 복제 (Clone)**

    ```bash
    git clone [your-repository-url]
    cd mission-restore
    ```

2.  **의존성 설치 (Install Dependencies)**

    `Poetry`를 사용하여 개발에 필요한 도구(Mypy, Ruff 등)를 설치합니다. 이 과정에서 가상 환경이 자동으로 생성됩니다.

    ```bash
    poetry install
    ```

3.  **📝 로그 파일 준비 (Prepare Your Log File)**

    복원할 대상인 **개발 과정 로그 파일** (예: `development.log`)을 프로젝트 내 원하는 위치에 준비합니다. `inputs` 디렉토리를 만들어 관리하는 것을 권장합니다.

    ```
    mission-restore/
    ├── inputs/
    │   └── development.log  <-- 여기에 로그 파일을 위치시키세요.
    └── src/
        └── ...
    ```

## 💻 사용 방법 (Usage)

복원은 터미널에서 다음 명령어를 통해 실행합니다. 총 2개의 인자(입력 파일, 출력 파일)가 필요합니다.

### 명령어 형식

```bash
poetry run python -m mission_restore.main [INPUT_FILE] [OUTPUT_FILE]
```

-   `INPUT_FILE`: 복원할 개발 과정 로그 파일의 경로 (예: `inputs/development.log`).
-   `OUTPUT_FILE`: 복원된 최종 코드가 저장될 파일 경로 (예: `output/restored_app.py`).

### 실행 예시

```bash
poetry run python -m mission_restore.main \
    ./inputs/development.log \
    ./output/restored_app.py
```

### 성공 시 출력 예시

```
[  INFO   ] 코드 복원 프로세스 (v4.3)를 시작합니다...
             - 입력 파일: ./inputs/development.log
             - 출력 파일: ./output/restored_app.py

[ STEP 1  ] 로그 파일에서 초기 코드와 변경 기록을 파싱합니다...
[   OK    ] 초기 버전 코드를 성공적으로 추출했습니다.
[   OK    ] 총 15개의 변경 기록(diff)을 찾았습니다.
[ STEP 2  ] 초기 코드에 변경 기록을 순차적으로 적용합니다...
[   ...   ] 패치 #1 적용 완료.
[   ...   ] 패치 #2 적용 완료.
...
[   ...   ] 패치 #15 적용 완료.
[ STEP 3  ] './output/restored_app.py' 파일에 결과를 저장합니다...
[ SUCCESS ] 최종 복원된 코드를 './output/restored_app.py' 파일로 저장했습니다.
```

## ⚙️ 동작 원리: 로그 파일의 구조

복원의 대상이 되는 로그 파일은 단순한 텍스트 파일이 아니라, 아래와 같은 명확한 구조를 가진 여러 개의 **블록(Block)**이 연속적으로 이어진 파일입니다.

```
[ Initial Code Block ] [ Diff Block #1 ] [ Diff Block #2 ] ...
```

각각의 블록은 다음과 같은 세부 형식으로 구성됩니다.

| 블록 종류 (Block Type)     | 구분 헤더 (Separator Header)               | 내용 (Content)                                                         |
| -------------------------- | ------------------------------------------ | ---------------------------------------------------------------------- |
| **초기 코드 블록**         | `🦊=== Initial version of [filename] ===`  | 이 헤더 아래에 위치한 모든 텍스트는 복원의 기초가 되는 초기 소스 코드입니다. |
| **변경 기록 (Diff) 블록**  | `--- previous version`<br>`+++ current version` | [Unified Diff Format](https://en.wikipedia.org/wiki/Diff#Unified_format) 형식의 코드 변경 사항. 헤더와 함께 하나의 묶음(패치)으로 처리됩니다. |

복원 유틸리티는 이 구조를 순서대로 파싱하며, 최종 코드를 재구성하기 위해 다음의 과정을 수행합니다.

1.  **초기 코드 파싱**: `Initial version` 블록을 찾아 전체 내용을 메모리로 로드합니다.
2.  **Diff 블록 탐색**: `---`/`+++` 헤더 쌍으로 시작하는 모든 `Diff` 블록을 순서대로 찾아 리스트로 만듭니다.
3.  **순차적 패치 적용**: 초기 코드를 시작으로, 각 `Diff` 블록(패치)을 순서대로 적용합니다.
4.  **컨텍스트 검증**: 각 패치를 적용할 때마다, 변경되지 않은 라인(컨텍스트 라인)이 현재 코드와 일치하는지 검사하여 무결성을 보장합니다.
5.  **최종 결과 저장**: 모든 패치 적용이 완료되면, 최종 결과물인 소스 코드를 지정된 출력 파일에 저장합니다.

## 📄 라이선스 (License)

이 프로젝트는 [MIT](LICENSE) 라이선스를 따릅니다.
