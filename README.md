# SimsimPC WebRTC signaling server

최초 WebRTC 연결 정보(Offer/Answer/ICE candidate) 전달용 서버입니다. GitHub에 소스를 저장하고 Cloudflare Workers + Durable Objects에 배포합니다.

**중요:** GitHub Pages 자체는 쓰기 가능한 시그널링 서버가 아닙니다. 이 코드를 GitHub에 올리는 것만으로 서버가 실행되지는 않습니다.

## 배포
1. Node.js 설치
2. `npx wrangler login`
3. `npx wrangler deploy`
4. 출력된 `https://...workers.dev`가 고정 HTTPS 시그널링 주소입니다.

## API
- `POST /rooms/{room}/join` body `{"peer":"controller","key":"16자 이상 공유 비밀"}`
- `POST /rooms/{room}/send` body `{"peer":"controller","key":"...","payload":{"type":"offer","sdp":"..."}}`
- `GET /rooms/{room}/poll?peer=target&key=...`  -> `{"messages":[...]}`

두 PC는 동일한 room ID와 key를 사용해야 합니다. 각 상대의 데이터는 1회 읽을 수 있는 큐로 전달됩니다. 문자/화면 데이터는 WebRTC 연결 후 P2P로 통신하며 이 서버는 전달하지 않습니다.

### 주의 (실험용)
- 이 서버는 테스트용입니다. 실제 고객 지원에 앞서 키 해싱, 만료, 세션 승인, 인증, 요청 제한 및 로그 정책 강화가 필요합니다.
- URL 쿼리의 key는 로그에 남을 수 있으므로 운영환경에서는 헤더 인증 방식으로 바꿔야 합니다.
- 방 저장 데이터는 현재 자동 만료/정리되지 않습니다. 테스트 후 관리 정책을 추가하세요.
