# 손님용 Customer 실행 안내

위치: C:\Users\김범석\Desktop\pc-mcp-pcp-main\Customer

```text
Customer/
├── server.py           # P2P 연결 대기 및 Staff 요청 실행
├── cor/
│   ├── mouse/, keyboard/, window/, system/, files/, ...
│   ├── screen/, verify/, watch/, interaction/, safety/, ...
│   ├── recording/, macro/
│   └── _runtime/       # 공통 실행·검사·기록 처리
├── config/
│   ├── server.json     # Worker 주소, Room ID
│   ├── permissions.json
│   └── defaults.json
├── dat/
│   ├── logs/
│   ├── tmp/
│   ├── screenshots/
│   └── state/          # 질문·감시·조작 기록·매크로 DB
├── requirements.txt
├── setup.ps1
└── start.ps1
```

현재 PC에는 의존성을 설치했습니다. Customer 폴더에서 `./start.ps1`을 실행하고 저장된 Room ID와 공유 키로 자동 연결됩니다. 다른 PC로 옮긴 경우 먼저 `./setup.ps1`을 실행합니다. Python 3.12를 권장합니다.

연결 주소: https://pc-mcp-pcp.gimbeomseognam5.workers.dev

Worker는 연결 정보만 중개합니다. PC 제어·화면·파일·명령 결과는 WebRTC P2P 데이터 채널로 전달합니다. Customer는 별도 공개 HTTP 제어 서버를 열지 않습니다. 공유 키는 config/server.json에 저장되어 자동 연결에 사용됩니다.

`server.py --list`는 PC 실행 기능 67개를 보여줍니다. Staff에 남는 작업 기록·로그·미션 등 14개와 합쳐 81개 기능입니다. `_runtime`은 공통 코드이고 나머지 기능 폴더의 run()을 서버가 호출합니다. 예전 코드 폴더 `_legacy`는 만들지 않았습니다.

손님 PC에서 차단할 기능은 config/permissions.json의 disabled에 files/delete.py 같은 경로로 넣습니다. config/defaults.json은 기능별 기본값을 설정합니다. 이 제한은 매크로 재생에도 적용됩니다.

Customer 런타임 데이터는 Customer/dat 한 곳에 저장합니다. Staff/dat는 직원 PC의 로그·작업 기록이므로 별개입니다. cor/_runtime 안에는 별도의 dat/data 폴더를 만들지 않습니다.

실제 로컬 WebRTC 연결을 통해 상태 조회, 임시 파일 생성·복사·읽기, 화면 캡처, 매크로 재생, 일반 PowerShell, 파일 감시와 긴급 중지를 검증했습니다. 다른 네트워크의 두 PC 연결 및 관리자 UAC 실물 승인은 별도 확인이 필요합니다. 긴급 중지 후 제어를 재개하려면 Customer를 다시 시작하세요.
