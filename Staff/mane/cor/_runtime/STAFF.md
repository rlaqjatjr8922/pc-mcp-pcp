# Staff 실행 안내

구현 위치: C:\Users\김범석\Desktop\pc-mcp-pcp-main\Staff

```text
Staff/
├── server.py          # 실행·인증·권한·요청 처리
├── cor/
│   ├── mouse/, keyboard/, window/, system/, files/, screen/, ...
│   ├── history/, log/, mission/, recording/, macro/, ...
│   ├── _runtime/      # 공통 처리, P2P 전송, 브라우저 화면
│   └── _legacy/       # 기존 테스트·시제품 보존
├── config/
│   ├── server.json    # 주소, 포트, API 키, signal_url
│   ├── permissions.json
│   └── defaults.json
├── dat/
│   ├── history/
│   ├── logs/          # 요청 기록 및 server.log
│   └── tmp/           # 임시 캡처
└── requirements.txt
```

Staff 폴더에서 `../.venv/Scripts/python.exe server.py`로 실행합니다. 입력한 Room ID와 공유 키는 Customer와 같아야 합니다. 시작하면 설정된 Worker에 접속해 P2P 연결을 시도합니다. 연결되지 않으면 서버는 계속 실행되며 다음 도구 요청에서 연결을 다시 확인합니다.

시그널링 주소: https://pc-mcp-pcp.gimbeomseognam5.workers.dev

Worker는 최초 연결 정보만 전달하며 PC 조작·화면·파일 데이터는 WebRTC P2P로 전달합니다. 현재 Worker 접속 확인 결과 HTTP 200을 받았습니다. Customer를 수정하거나 실제 고객 방에 연결하지는 않았습니다.

`server.py --list`로 등록된 81개 도구를 확인할 수 있습니다. 브라우저 제어 주소는 http://127.0.0.1:8765/control, MCP 주소는 http://127.0.0.1:8765/mcp 입니다. API 키는 config/server.json에 있습니다.

기존 데이터는 dat로 옮겨 보존했습니다. 파일 복사의 이전 overwrite 기본값은 새로운 options.overwrite 형태로 적용합니다. 환경변수 PC_SIGNAL, PC_ROOM, PC_SHARED_KEY를 지정할 수도 있습니다.

다른 네트워크의 실제 Customer 연결에는 상대 PC 실행과 같은 Room ID·공유 키가 필요합니다. 이 작업에서는 Worker 주소 응답과 로컬 P2P 통합 테스트를 확인했습니다.
