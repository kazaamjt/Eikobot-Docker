"""
Models for deploying and managing Docker on a remote host.
"""
from pathlib import Path

from eikobot.core.handlers import CRUDHandler, HandlerContext
from eikobot.core.helpers import EikoBaseModel
from eikobot.core.lib.std import CmdResult, HostModel

_INSTALL_SCRIPT_DIR = Path(__file__).parent / "install_scripts"


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
        script = (_INSTALL_SCRIPT_DIR / "debian.sh").read_text()
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
