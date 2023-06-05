"""
Models for deploying and managing Docker on a remote host.
"""
from pathlib import Path

import aiohttp
from eikobot.core.handlers import CRUDHandler, HandlerContext
from eikobot.core.helpers import EikoBaseModel
from eikobot.core.lib.std import CmdResult, HostModel
from eikobot.core.lib.std.file import FileModel

_FILES_DIR = Path(__file__).parent / "files"
_HTTP_TIMEOUT = aiohttp.ClientTimeout(10)


async def _verify_install(ctx: HandlerContext, host: HostModel) -> bool:
    docker_version = await host.execute("sudo docker --version", ctx)
    return docker_version.returncode == 0


class DockerInstaller(EikoBaseModel):
    """
    Model that represents a docker installation
    perfromed by Eikobot.
    """

    __eiko_resource__ = "DockerInstaller"

    host: HostModel


class DockerInstallerHandler(CRUDHandler):
    """
    Installs docker on a remote host.
    """

    __eiko_resource__ = "DockerInstaller"

    async def _install(self, ctx: HandlerContext, host: HostModel) -> bool:
        """
        Install docker on a remote host.
        """
        if host.os_name.resolve(str) == "debian":
            result = await self._install_debian(ctx, host)
        else:
            ctx.error(f"OS '{host.os_name.resolve(str)}' is currently not supported.")
            return False

        if result.failed():
            return False

        return await _verify_install(ctx, host)

    async def _install_debian(self, ctx: HandlerContext, host: HostModel) -> CmdResult:
        script = (_FILES_DIR / "debian.sh").read_text()
        return await host.script(script, "bash", ctx)

    async def create(self, ctx: HandlerContext) -> None:
        if not isinstance(ctx.resource, DockerInstaller):
            ctx.failed = True
            return

        if not await self._install(ctx, ctx.resource.host):
            ctx.failed = True
            return

        ctx.deployed = True

    async def read(self, ctx: HandlerContext) -> None:
        if not isinstance(ctx.resource, DockerInstaller):
            ctx.failed = True
            return

        if not await _verify_install(ctx, ctx.resource.host):
            return

        ctx.deployed = True


class DockerHostModel(EikoBaseModel):
    """
    Model that represents a docker installation
    perfromed by Eikobot.
    """

    __eiko_resource__ = "DockerHost"

    host: HostModel
    install: bool
    docker_port: int = 2376


class DockerHostHandler(CRUDHandler):
    """
    Configures docker on a remote host.
    """

    __eiko_resource__ = "DockerHost"

    async def __pre__(self, ctx: HandlerContext) -> None:
        if not isinstance(ctx.resource, DockerHostModel):
            ctx.failed = True
            return

        if ctx.resource.host.host not in ["127.0.0.1", "localhost"]:
            await ctx.resource.host.forward_port(
                ctx, ctx.resource.docker_port, ctx.resource.docker_port
            )

    async def create(self, ctx: HandlerContext) -> None:
        if not isinstance(ctx.resource, DockerHostModel):
            ctx.failed = True
            return

        await ctx.resource.host.execute(
            "sudo systemctl daemon-reload",
            ctx,
        )
        await ctx.resource.host.execute(
            "sudo systemctl restart docker",
            ctx,
        )

        async with aiohttp.ClientSession(timeout=_HTTP_TIMEOUT) as session:
            response = await session.get(
                f"http://127.0.0.1:{ctx.resource.docker_port}/info"
            )
            if response.status == 200:
                ctx.deployed = True

    async def read(self, ctx: HandlerContext) -> None:
        if not isinstance(ctx.resource, DockerHostModel):
            ctx.failed = True
            return

        if ctx.resource.host.os_platform.resolve(str) != "linux-gnu":
            ctx.error(
                f"OS '{ctx.resource.host.os_platform.resolve(str)}' is currently not supported."
            )
            ctx.failed = True
            return

        async with aiohttp.ClientSession(timeout=_HTTP_TIMEOUT) as session:
            try:
                response = await session.get(
                    f"http://127.0.0.1:{ctx.resource.docker_port}/info"
                )
                if response.status == 200:
                    ctx.deployed = True
            except aiohttp.ClientConnectionError:
                return

    async def __post__(self, ctx: HandlerContext) -> None:
        if not isinstance(ctx.resource, DockerHostModel):
            ctx.failed = True
            return

        if ctx.resource.host.host not in ["127.0.0.1", "localhost"]:
            await ctx.resource.host.stop_forwarding_port(
                ctx,
                ctx.resource.docker_port,
            )
