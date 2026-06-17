import asyncio
import os
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

class SyncMCPClient:
    """
    동기(Synchronous) 환경인 AMEVA Window Assistant에서 
    비동기(Async) 기반의 공식 MCP SDK를 쉽게 사용할 수 있도록 감싸주는 래퍼 클래스.
    """
    def __init__(self, script_path: str):
        self.script_path = script_path
        self._cached_env = None
        
    def _get_mcp_env(self) -> dict:
        """Fetch Secrets via Hybrid Architecture (Memory Hijacking + Vault Fallback)"""
        if self._cached_env is not None:
            return self._cached_env
            
        env = os.environ.copy()
        token = None
        
        # 1. 1st Priority: Memory Hijacking via git credential fill
        try:
            import subprocess
            proc = subprocess.run(
                ["git", "credential", "fill"],
                input="url=https://github.com\n\n",
                capture_output=True,
                text=True,
                timeout=5
            )
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    if line.startswith("password="):
                        token = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
            
        # 2. 2nd Priority: Vault Fallback
        if not token:
            try:
                from src.storage.db import DatabaseManager
                from src.storage.secret_manager import SecretManager
                db = DatabaseManager(r"C:\ameva\AMEVA-Window-Assistant\ameva_assistant.db")
                sm = SecretManager()
                enc_token = db.get_secret("github_master_token")
                if enc_token:
                    token = sm.decrypt(enc_token)
            except Exception:
                pass
                
        if token:
            env["AMEVA_GITHUB_TOKEN"] = token
            
        self._cached_env = env
        return env

    def _get_git_identity(self) -> tuple:
        import subprocess
        name, email = "AMEVA Agent", "agent@ameva.ai"
        try:
            res_name = subprocess.run(["git", "config", "--global", "user.name"], capture_output=True, text=True, timeout=2)
            if res_name.returncode == 0 and res_name.stdout.strip():
                name = res_name.stdout.strip()
            res_email = subprocess.run(["git", "config", "--global", "user.email"], capture_output=True, text=True, timeout=2)
            if res_email.returncode == 0 and res_email.stdout.strip():
                email = res_email.stdout.strip()
        except Exception:
            pass
        return name, email

    def _get_server_params(self) -> StdioServerParameters:
        token = self._get_mcp_env().get("AMEVA_GITHUB_TOKEN", "")
        git_name, git_email = self._get_git_identity()
        return StdioServerParameters(
            command="docker",
            args=[
                "run",
                "-i",
                "--rm",
                "-v",
                r"C:\ameva:/app/workspace",
                "-e",
                "AMEVA_IN_CONTAINER=true",
                "-e",
                f"AMEVA_GITHUB_TOKEN={token}",
                "-e",
                f"GIT_AUTHOR_NAME={git_name}",
                "-e",
                f"GIT_AUTHOR_EMAIL={git_email}",
                "-e",
                f"GIT_COMMITTER_NAME={git_name}",
                "-e",
                f"GIT_COMMITTER_EMAIL={git_email}",
                "ameva-mcp-server"
            ],
            env={}
        )


    def execute_tool(self, tool_name: str, arguments: dict) -> str:
        async def _run():
            server_params = self._get_server_params()
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    if result.isError:
                        return f"Error: {result.content}"
                    else:
                        texts = [getattr(c, 'text', str(c)) for c in result.content if getattr(c, 'type', '') == 'text']
                        if not texts:
                            return str(result.content)
                        return "\n".join(texts)
                        
        return asyncio.run(_run())
        
    def get_tools(self) -> list:
        async def _get():
            server_params = self._get_server_params()
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    openai_tools = []
                    for t in result.tools:
                        openai_tools.append({
                            "type": "function",
                            "function": {
                                "name": t.name,
                                "description": t.description or "",
                                "parameters": t.inputSchema
                            }
                        })
                    return openai_tools
        return asyncio.run(_get())
