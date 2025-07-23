import aiohttp
import asyncio
from types import TracebackType
from typing import Self, Type
from loguru import logger

from .cards import launch_card_factory, finish_card_factory

__all__ = [
    "BaseBot",
    "Bot",
    "BotNowait",
]


class BaseBot:

    def __init__(
        self,
        url: str,
        *,
        delay: float = 1.0,
    ) -> None:
        self._url = url
        self._delay = delay
        self._que = asyncio.Queue()
        self._sess = aiohttp.ClientSession()
        self._task = None

    async def __aenter__(
        self,
    ) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        await self.stop()
        await self._sess.close()

    async def _engine(
        self,
    ) -> None:
        pass

    async def start(
        self,
    ) -> None:
        logger.info(f"{self} starting")
        if self.running:
            logger.warning(f"{self} have started")
            return
        self._task = asyncio.create_task(self._engine())
        logger.info(f"{self} started")

    async def stop(
        self,
    ) -> None:
        logger.info(f"{self} stopping")
        if not self.running:
            logger.warning(f"{self} have stopped")
            return
        await self._que.join()
        self._task.cancel()
        self._task = None
        logger.info(f"{self} stopped")

    @property
    def running(
        self,
    ) -> bool:
        return not (self._task is None or self._task.cancelled() or self._task.done())

    @property
    def closed(
        self,
    ) -> bool:
        return self._sess.closed


class Bot(BaseBot):

    async def start(
        self,
    ) -> None:
        if self.running:
            return
        res = await super().start()
        await self.send_interactive(launch_card_factory())
        return res

    async def stop(
        self,
    ) -> None:
        if not self.running:
            return
        await self.send_interactive(finish_card_factory())
        await super().stop()

    async def _engine(
        self,
    ) -> None:
        url = self._url
        delay = self._delay
        while True:
            payload = await self._que.get()
            logger.info(f"payload: {str(payload)[:256]}")
            max_tries = 3
            for _ in range(max_tries):
                await asyncio.sleep(delay)
                resp = await self._sess.post(url, json=payload)
                status = resp.status
                reason = resp.reason
                headers = resp.headers
                text = await resp.text()
                if not resp.ok:
                    logger.warning(f"{status} {reason}\n{text}")
                    continue
                data = await resp.json()
                if not isinstance(data, dict) or 0 != data.get("code"):
                    logger.warning(f"{status} {reason}\n{text}")
                    continue
                logger.success(f"{status} {reason}\n{text}")
                break
            else:
                logger.error(f"{status} {reason}\n{headers}\n{text}")
            self._que.task_done()

    async def send_text(
        self,
        text: str,
    ) -> None:
        payload = {"msg_type": "text", "content": {"text": text}}
        await self._que.put(payload)

    async def send_post(
        self,
        post: dict,
    ) -> None:
        payload = {"msg_type": "post", "content": {"post": post}}
        await self._que.put(payload)

    async def send_share_chat(
        self,
        share_chat_id: str,
    ) -> None:
        payload = {
            "msg_type": "share_chat",
            "content": {"share_chat_id": share_chat_id},
        }
        await self._que.put(payload)

    async def send_image(
        self,
        image_key: str,
    ) -> None:
        payload = {"msg_type": "image", "content": {"image_key": image_key}}
        await self._que.put(payload)

    async def send_interactive(
        self,
        card: dict,
    ) -> None:
        payload = {"msg_type": "interactive", "card": card}
        await self._que.put(payload)


class BotNowait(BaseBot):

    async def start(
        self,
    ) -> None:
        if self.running:
            return
        res = await super().start()
        self.send_interactive(launch_card_factory())
        return res

    async def stop(
        self,
    ) -> None:
        if not self.running:
            return
        self.send_interactive(finish_card_factory())
        await super().stop()

    async def _engine(
        self,
    ) -> None:
        url = self._url
        delay = self._delay
        while True:
            await asyncio.sleep(1.0)
            if self._que.empty():
                continue
            payload = self._que.get_nowait()
            logger.info(f"payload: {str(payload)[:256]}")
            max_tries = 3
            for _ in range(max_tries):
                await asyncio.sleep(delay)
                resp = await self._sess.post(url, json=payload)
                status = resp.status
                reason = resp.reason
                headers = resp.headers
                text = await resp.text()
                if not resp.ok:
                    logger.warning(f"{status} {reason}\n{text}")
                    continue
                data = await resp.json()
                if not isinstance(data, dict) or 0 != data.get("code"):
                    logger.warning(f"{status} {reason}\n{text}")
                    continue
                logger.success(f"{status} {reason}\n{text}")
                break
            else:
                logger.error(f"{status} {reason}\n{headers}\n{text}")
            self._que.task_done()

    def send_text(
        self,
        text: str,
    ) -> None:
        payload = {"msg_type": "text", "content": {"text": text}}
        self._que.put_nowait(payload)

    def send_post(
        self,
        post: dict,
    ) -> None:
        payload = {"msg_type": "post", "content": {"post": post}}
        self._que.put_nowait(payload)

    def send_share_chat(
        self,
        share_chat_id: str,
    ) -> None:
        payload = {
            "msg_type": "share_chat",
            "content": {"share_chat_id": share_chat_id},
        }
        self._que.put_nowait(payload)

    def send_image(
        self,
        image_key: str,
    ) -> None:
        payload = {"msg_type": "image", "content": {"image_key": image_key}}
        self._que.put_nowait(payload)

    def send_interactive(
        self,
        card: dict,
    ) -> None:
        payload = {"msg_type": "interactive", "card": card}
        self._que.put_nowait(payload)
