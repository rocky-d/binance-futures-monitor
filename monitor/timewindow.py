import collections

__all__ = [
    "TimewindowEmpty",
    "Timewindow",
    "SparseTimewindow",
]


class TimewindowEmpty(Exception):
    pass


class Timewindow[U]:

    def __init__(
        self,
        interval: int,
    ) -> None:
        self._interval = interval
        self._us = collections.deque()
        self._ts = collections.deque()

    @property
    def interval(
        self,
    ) -> int:
        return self._interval

    def _add(
        self,
        u: U,
        t: int,
    ) -> None:
        self._us.append(u)
        self._ts.append(t)

    def _del(
        self,
        t: int,
    ) -> None:
        us = self._us
        ts = self._ts
        t -= self._interval
        while 0 < len(ts) and ts[0] < t:
            us.popleft()
            ts.popleft()

    def push(
        self,
        u: U,
        t: int,
    ) -> None:
        self._del(t)
        self._add(u, t)

    def empty(
        self,
    ) -> bool:
        return 0 == len(self._us)

    def head(
        self,
    ) -> tuple[U, int]:
        if self.empty():
            raise TimewindowEmpty
        return self._us[0], self._ts[0]

    def tail(
        self,
    ) -> tuple[U, int]:
        if self.empty():
            raise TimewindowEmpty
        return self._us[-1], self._ts[-1]


class SparseTimewindow[U](Timewindow):

    def __init__(
        self,
        interval,
        *,
        unit: int = 0,
    ) -> None:
        super().__init__(interval)
        self._unit = unit

    @property
    def unit(
        self,
    ) -> int:
        return self._unit

    def push(
        self,
        u: U,
        t: int,
    ) -> None:
        if not self.empty() and t - self.tail()[1] < self._unit:
            return
        super().push(u, t)
