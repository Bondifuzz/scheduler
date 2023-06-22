from __future__ import annotations
from typing import TYPE_CHECKING

import sys
import random
import logging
from collections import deque
from scheduler.app.message_queue.state import MQAppState
from scheduler.app.scheduler.base import ScheduleEmptyError, SchedulerBase
from asyncio import Lock

from scheduler.app.settings import AppSettings

if TYPE_CHECKING:
    from mqtransport import MQApp
    from scheduler.app.database.orm import ORMFuzzer
    from typing import Optional, List, Dict


class DistanceFuzzerNode:
    fuzzer: ORMFuzzer
    cur_weight: int
    map_id: int

    tick_cnt: int
    runs_cnt: int

    def __init__(self, fuzzer: ORMFuzzer, map_id: int):
        self.fuzzer = fuzzer
        self.cur_weight = 0
        self.reset(map_id)

    def reset(self, map_id: int):
        self.map_id = map_id
        self.tick_cnt = 0
        self.runs_cnt = 0

    def tick(self, weight_sum: int, window_size: int) -> float:
        if self.tick_cnt < window_size:
            self.tick_cnt += 1
        elif self.tick_cnt > window_size:
            self.tick_cnt = window_size

        if self.cur_weight == 0:
            distance = 0
        else:
            distance = (self.cur_weight / weight_sum) - (
                self.runs_cnt / self.tick_cnt
            )

        return distance


class DistanceScheduler(SchedulerBase):

    window_size: int

    weight_sum: int
    fuzzers: Dict[str, ORMFuzzer]
    fuzzer_nodes: Dict[str, DistanceFuzzerNode]

    fuzz_map_counter: int
    fuzz_map: Dict[int, str]

    runs: deque

    _lock: Lock
    _settings: AppSettings

    def __init__(self, state: MQAppState, fuzzers: List[ORMFuzzer] = list()) -> None:
        self._lock = Lock()
        self._logger = logging.getLogger("WeightQueue")
        self._settings = state.settings

        self.window_size = 0
        self.weight_sum = 0

        self.fuzzers = {}
        self.fuzzer_nodes = {}

        self.fuzz_map = {}
        self.fuzz_map_counter = 0

        self.runs = deque()

        for fuzzer in fuzzers:
            if fuzzer.is_verified:
                self._start_fuzzer(fuzzer)


    def _stop_fuzzer(self, fuzzer_id: str) -> None:
        fuzz_node = self.fuzzer_nodes.pop(fuzzer_id, None)
        self.fuzzers.pop(fuzzer_id, None)

        if fuzz_node is not None:
            self.fuzz_map.pop(fuzz_node.map_id, None)
            self.weight_sum -= fuzz_node.cur_weight

            self.window_size = (
                len(self.fuzz_map) * self._settings.scheduler.max_weight
            )
    

    def _start_fuzzer(self, fuzzer: ORMFuzzer) -> None:
        self._stop_fuzzer(fuzzer.id)

        self.fuzzers[fuzzer.id] = fuzzer
        self.fuzzer_nodes[fuzzer.id] = DistanceFuzzerNode(
            fuzzer, self.fuzz_map_counter
        )

        self.fuzz_map[self.fuzz_map_counter] = fuzzer.id
        self.fuzz_map_counter += 1

        self.fuzzer_nodes[fuzzer.id].cur_weight = fuzzer.state.weight
        self.weight_sum += fuzzer.state.weight
        self.window_size = (
            len(self.fuzz_map) * self._settings.scheduler.max_weight
        )


    def _update_weight(self, fuzzer_id: str) -> None:
        fuzz_node = self.fuzzer_nodes.get(fuzzer_id, None)
        if fuzz_node is None:
            return

        if fuzz_node.cur_weight == fuzz_node.fuzzer.state.weight:
            return

        self.weight_sum -= fuzz_node.cur_weight
        self.weight_sum += fuzz_node.fuzzer.state.weight
        fuzz_node.cur_weight = fuzz_node.fuzzer.state.weight

        del self.fuzz_map[fuzz_node.map_id]
        self.fuzz_map[self.fuzz_map_counter] = fuzz_node.fuzzer.id
        self.fuzzer_nodes[fuzz_node.fuzzer.id].reset(self.fuzz_map_counter)
        self.fuzz_map_counter += 1

    async def start_fuzzer(self, fuzzer: ORMFuzzer) -> None:
        async with self._lock:
            self._start_fuzzer(fuzzer)

    async def stop_fuzzer(self, fuzzer_id: str) -> None:
        async with self._lock:
            self._stop_fuzzer(fuzzer_id)

    async def update_weight(self, fuzzer_id: str) -> None:
        async with self._lock:
            self._update_weight(fuzzer_id)

    async def choose_next(self) -> Optional[ORMFuzzer]:
        async with self._lock:
            if len(self.fuzz_map) == 0 or self.weight_sum == 0:
                return None
                # raise ScheduleEmptyError("No fuzzers to run")

            tmp_ids: List[str] = []
            tmp_weights: List[int] = []
            best_neg_distance = -(sys.maxsize - 1)

            sel_map_id = None

            for map_id in self.fuzz_map:
                fuzz_id = self.fuzz_map[map_id]

                # skip first-run fuzzers
                if self.fuzzer_nodes[fuzz_id].cur_weight == 0:
                    continue

                distance = self.fuzzer_nodes[fuzz_id].tick(
                    self.weight_sum, self.window_size
                )

                if distance > 0:
                    tmp_ids.append(map_id)
                    tmp_weights.append(distance)
                else:
                    if distance > best_neg_distance:
                        best_neg_distance = distance
                        sel_map_id = map_id

            if len(tmp_ids) > 0:
                sel_map_id = random.choices(
                    population=tmp_ids, weights=tmp_weights, k=1
                )[0]
            elif sel_map_id is None:
                return None

            self.fuzzer_nodes[self.fuzz_map[sel_map_id]].runs_cnt += 1
            self.runs.append(sel_map_id)

            while len(self.runs) > self.window_size:
                map_id = self.runs.popleft()
                if map_id in self.fuzz_map:
                    self.fuzzer_nodes[self.fuzz_map[map_id]].runs_cnt -= 1

            return self.fuzzers[self.fuzz_map[sel_map_id]]


    async def try_revert_run(self, fuzzer_id: str):
        async with self._lock:
            fuzz_node = self.fuzzer_nodes.get(fuzzer_id, None)
            if fuzz_node is None:
                return

            fuzz_node.runs_cnt = max(0, fuzz_node.runs_cnt - 1)
