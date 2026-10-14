// WebRTC signaling relay. Run on Cloudflare Workers + Durable Objects.
// No WebRTC chat/desktop data is relayed here.
const cors = {"access-control-allow-origin":"*","access-control-allow-methods":"GET, POST, OPTIONS","access-control-allow-headers":"content-type","cache-control":"no-store"};
const json = (data,status=200)=>new Response(JSON.stringify(data),{status,headers:{...cors,"content-type":"application/json"}});
export default {
  async fetch(request,env){
    if(request.method==="OPTIONS")return new Response(null,{headers:cors});
    const url=new URL(request.url);
    if(url.pathname==="/")return json({service:"simsimpc-webrtc-signal",endpoints:["POST /rooms/{room}/join","POST /rooms/{room}/send","GET /rooms/{room}/poll?peer=...&key=..."]});
    const match=url.pathname.match(/^\/rooms\/([a-zA-Z0-9_-]{8,80})\/(join|send|poll)$/);
    if(!match)return json({error:"not found"},404);
    const id=env.ROOM.idFromName(match[1]);
    const stub=env.ROOM.get(id);
    return stub.fetch(request);
  }
};

export class SignalRoom {
  constructor(state){this.state=state;}
  async fetch(request){
    const url=new URL(request.url);
    const action=url.pathname.split("/").pop();
    if(action==="join"&&request.method==="POST"){
      const body=await request.json().catch(()=>({}));
      const peer=body.peer;
      const key=body.key;
      if(!["controller","target"].includes(peer)||typeof key!=="string"||key.length<16)return json({error:"peer or key invalid"},400);
      const saved=await this.state.storage.get("key");
      if(saved&&saved!==key)return json({error:"wrong room key"},403);
      if(!saved)await this.state.storage.put("key",key);
      // A room is a small demonstration. Access requires knowledge of room id and shared key.
      await this.state.storage.put("last_"+peer,Date.now());
      return json({ok:true,peer});
    }
    if(action==="send"&&request.method==="POST"){
      const body=await request.json().catch(()=>({}));
      const {peer,key,payload}=body;
      if(!["controller","target"].includes(peer)||typeof key!=="string"||key!==(await this.state.storage.get("key")))return json({error:"unauthorized"},403);
      if(!payload||!["offer","answer","candidate","end-of-candidates"].includes(payload.type))return json({error:"invalid signal"},400);
      const destination=peer==="controller"?"target":"controller";
      const queue=(await this.state.storage.get("queue_"+destination))||[];
      if(queue.length>=100)return json({error:"queue full"},429);
      queue.push({from:peer,payload,ts:Date.now()});
      await this.state.storage.put("queue_"+destination,queue);
      return json({ok:true});
    }
    if(action==="poll"&&request.method==="GET"){
      const peer=url.searchParams.get("peer"),key=url.searchParams.get("key");
      if(!["controller","target"].includes(peer)||typeof key!=="string"||key!==(await this.state.storage.get("key")))return json({error:"unauthorized"},403);
      const name="queue_"+peer;
      const queue=(await this.state.storage.get(name))||[];
      await this.state.storage.put(name,[]);
      return json({messages:queue});
    }
    return json({error:"method not allowed"},405);
  }
}
