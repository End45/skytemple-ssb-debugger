#  Copyright 2020 Parakoopa
#
#  This file is part of SkyTemple.
#
#  SkyTemple is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SkyTemple is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SkyTemple.  If not, see <https://www.gnu.org/licenses/>.
import asyncio
from threading import Lock
from typing import Iterable

import cairo

from desmume.emulator import DeSmuME
from skytemple_ssb_debugger.controller.debugger import DebuggerController
from skytemple_ssb_debugger.emulator_thread import FRAMES_PER_SECOND
from skytemple_ssb_debugger.threadsafe import threadsafe_emu, threadsafe_emu_nonblocking, synchronized, \
    threadsafe_emu_nonblocking_coro

ALPHA_T = 0.7
COLOR_ACTOR = (255, 0, 255, ALPHA_T)
COLOR_OBJECTS = (255, 160, 0, ALPHA_T)
COLOR_PERFORMER = (0, 255, 255, ALPHA_T)
COLOR_EVENTS = (0, 0, 255, 100)
COLOR_BLACK = (0, 0, 0, ALPHA_T)
COLOR_POS_MARKERS = (0, 255, 0, ALPHA_T)
REDRAW_DELAY = 2


debug_overlay_lock = Lock()


class DebugOverlayController:
    def __init__(self, debugger: DebuggerController):
        self.debugger = debugger

        self.enabled = False
        self.visible = False

        self._refresh_cache = True
        self._cache_running = False
        self._cache_redrawing_registered = False
        self._actor_bbox_cache = []
        self._object_bbox_cache = []
        self._perf_bbox_cache = []
        self._event_bbox_cache = []

    def toggle(self, state):
        self.enabled = state

    @synchronized(debug_overlay_lock)
    def draw(self, ctx: cairo.Context, display_id: int):
        # TODO: Support other display drawing.
        if display_id == 1 and self.enabled and self.debugger:
            if self._refresh_cache and not self._cache_redrawing_registered:
                self._cache_redrawing_registered = True
                threadsafe_emu_nonblocking_coro(self.debugger.emu_thread, self._update_cache())

            if self._cache_running:
                # Draw
                for bbox in self._actor_bbox_cache:
                    ctx.set_source_rgba(*COLOR_ACTOR)
                    ctx.rectangle(
                        bbox[0], bbox[1],
                        bbox[2] - bbox[0], bbox[3] - bbox[1]
                    )
                    ctx.fill()
                for bbox in self._object_bbox_cache:
                    ctx.set_source_rgba(*COLOR_OBJECTS)
                    ctx.rectangle(
                        bbox[0], bbox[1],
                        bbox[2] - bbox[0], bbox[3] - bbox[1]
                    )
                    ctx.fill()
                for bbox in self._perf_bbox_cache:
                    ctx.set_source_rgba(*COLOR_PERFORMER)
                    ctx.rectangle(
                        bbox[0], bbox[1],
                        bbox[2] - bbox[0], bbox[3] - bbox[1]
                    )
                    ctx.fill()
                for bbox in self._event_bbox_cache:
                    ctx.set_source_rgba(*COLOR_EVENTS)
                    ctx.rectangle(
                        bbox[0], bbox[1],
                        bbox[2] - bbox[0], bbox[3] - bbox[1]
                    )
                    ctx.fill()
                # TODO: Position markers

    def break_pulled(self):
        """The debugger is stopped, the emulator is frozen."""
        self._refresh_cache = False

    def break_released(self):
        """The debugger is no longer stopped."""
        self._refresh_cache = True

    async def _update_cache(self):
        # Refresh the cache
        with debug_overlay_lock:
            ges = self.debugger.ground_engine_state
            self._cache_running = ges.running
            if self._cache_running:
                self._actor_bbox_cache = []
                self._object_bbox_cache = []
                self._perf_bbox_cache = []
                self._event_bbox_cache = []
                for actor in not_none(ges.actors):
                    self._actor_bbox_cache.append(actor.get_bounding_box_camera(ges.map))
                for object in not_none(ges.objects):
                    self._object_bbox_cache.append(object.get_bounding_box_camera(ges.map))
                for performer in not_none(ges.performers):
                    self._perf_bbox_cache.append(performer.get_bounding_box_camera(ges.map))
                for event in not_none(ges.events):
                    self._event_bbox_cache.append(event.get_bounding_box_camera(ges.map))

        if self._refresh_cache:
            await asyncio.sleep(1 / FRAMES_PER_SECOND * REDRAW_DELAY, loop=self.debugger.emu_thread.loop    )
            threadsafe_emu_nonblocking_coro(self.debugger.emu_thread, self._update_cache())
        else:
            self._cache_redrawing_registered = False


def not_none(it: Iterable):
    for i in it:
        if i is not None:
            yield i
