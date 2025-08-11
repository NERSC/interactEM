import asyncio
import json
import socket
from enum import Enum

from pydantic import BaseModel, ValidationError

# Maximum message size for client requests
MAX_MESSAGE_SIZE = 512

class MessageAction(str, Enum):
    REGISTER = "REGISTER"
    QUERY = "QUERY"
    UNREGISTER = "UNREGISTER"

class ResponseStatus(str, Enum):
    OK = "OK"
    ERROR = "ERROR"
    NOT_FOUND = "NOT_FOUND"

# Pydantic models for message validation
class RegisterMessage(BaseModel):
    action: MessageAction
    agent_id: str
    cxi_address: str

class QueryMessage(BaseModel):
    action: MessageAction
    agent_id: str

class UnregisterMessage(BaseModel):
    action: MessageAction
    agent_id: str

class BaseResponse(BaseModel):
    status: ResponseStatus
    message: str | None = None

    def model_dump_json(self, **kwargs) -> str:
        kwargs.setdefault('exclude_none', True)
        return super().model_dump_json(**kwargs)

class QueryResponse(BaseResponse):
    cxi_address: str | None = None

def get_primary_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't have to be reachable, just used to get the local IP
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

class CXIRegistryServer:
    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.registry: dict[str, str] = {}
        self.lock = asyncio.Lock()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            data = await reader.read(MAX_MESSAGE_SIZE)
            if not data:
                response = BaseResponse(status=ResponseStatus.ERROR, message="No data received")
                writer.write((response.model_dump_json() + "\n").encode())
                await writer.drain()
                return

            try:
                message_data = json.loads(data.decode().strip())
            except json.JSONDecodeError:
                response = BaseResponse(status=ResponseStatus.ERROR, message="Invalid JSON format")
                writer.write((response.model_dump_json() + "\n").encode())
                await writer.drain()
                return

            try:
                action = message_data.get("action")

                if action == MessageAction.REGISTER:
                    message = RegisterMessage(**message_data)
                    async with self.lock:
                        self.registry[message.agent_id] = message.cxi_address
                    response = BaseResponse(status=ResponseStatus.OK)

                elif action == MessageAction.QUERY:
                    message = QueryMessage(**message_data)
                    async with self.lock:
                        cxi_address = self.registry.get(message.agent_id)

                    if cxi_address:
                        response = QueryResponse(status=ResponseStatus.OK, cxi_address=cxi_address)
                    else:
                        response = BaseResponse(status=ResponseStatus.NOT_FOUND, message="Agent not found")

                elif action == MessageAction.UNREGISTER:
                    message = UnregisterMessage(**message_data)
                    async with self.lock:
                        removed = self.registry.pop(message.agent_id, None)

                    if removed:
                        response = BaseResponse(status=ResponseStatus.OK)
                    else:
                        response = BaseResponse(status=ResponseStatus.NOT_FOUND, message="Agent not found")

                else:
                    response = BaseResponse(status=ResponseStatus.ERROR, message="Invalid action")

            except ValidationError as e:
                response = BaseResponse(status=ResponseStatus.ERROR, message=f"Validation error: {str(e)}")

            writer.write((response.model_dump_json() + "\n").encode())
            await writer.drain()

        except Exception as e:
            response = BaseResponse(status=ResponseStatus.ERROR, message=str(e))
            writer.write((response.model_dump_json() + "\n").encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def run(self):
        primary_ip = get_primary_ip()
        print(f"CXIRegistryServer starting on {self.host}:{self.port}")
        print(f"Detected primary IP address: {primary_ip}")

        server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )

        addr = server.sockets[0].getsockname()
        print(f"CXIRegistryServer running on {addr[0]}:{addr[1]}")

        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(CXIRegistryServer().run())
