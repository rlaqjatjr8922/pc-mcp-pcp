"""MCP images are image content blocks, never base64 text dumps."""
import base64
import capture_store
import json
import hashlib
from io import BytesIO
from PIL import Image
from mcp.types import CallToolResult, TextContent, ImageContent

def image_response(result):
    """Inventory-style envelope shared by HTTP and native MCP image output."""
    if isinstance(result, dict) and result.get('encoding') in ('base64', 'local_file') and result.get('content_type','').split(';')[0].startswith('image/'):
        result = dict(result)
        raw = capture_store.image_bytes(result)
        if len(raw) > 32 * 1024 * 1024:
            raise ValueError('이미지가 너무 큽니다. 작은 영역을 캡처해 주세요.')
        with Image.open(BytesIO(raw)) as source:
            source.load()
            original = source.size
            mime = Image.MIME.get(source.format)
            if mime is None:
                raise ValueError('지원하지 않는 이미지 형식입니다.')
            # Send exactly the bytes read from the saved file: no resize,
            # re-encoding, optimization, or JPEG conversion.
            encoded = base64.b64encode(raw).decode('ascii')
            meta = {k:v for k,v in result.items() if k not in ('data','encoding','content_type','bytes')}
            meta.update(original_width=original[0], original_height=original[1], width=original[0], height=original[1],
                        content_type=mime, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                        coordinate_note='저장된 원본 이미지 그대로입니다. 이미지 좌표와 화면 좌표의 크기가 같습니다.')
            meta['image_id'] = meta['capture_id']
            meta['screenshot_id'] = meta['capture_id']
        return {'metadata': meta, 'content_items': [
            {'type':'text','text':json.dumps(meta,ensure_ascii=False)},
            {'type':'image','mimeType':mime,'data':encoded},
        ]}
    return None

def build(result):
    response = image_response(result)
    if response is not None:
        return CallToolResult(content=[TextContent(**response['content_items'][0]),
                                       ImageContent(**response['content_items'][1])],
                              structuredContent=response['metadata'])
    return CallToolResult(content=[TextContent(type='text',text=json.dumps(result,ensure_ascii=False))], structuredContent=result)
