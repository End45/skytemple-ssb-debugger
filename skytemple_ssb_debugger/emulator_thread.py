"""Object that manages the emulator thread."""
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
import traceback
from asyncio import Future
from threading import Thread, current_thread, Lock

import nest_asyncio

from desmume import controls
from desmume.emulator import DeSmuME
from skytemple_ssb_debugger.model.settings import DebuggerSettingsStore
from skytemple_ssb_debugger.threadsafe import THREAD_DEBUG, threadsafe_gtk_nonblocking, synchronized

TICKS_PER_FRAME = 17
FRAMES_PER_SECOND = 60


start_lock = Lock()
display_buffer_lock = Lock()
fps_frame_count_lock = Lock()


class EmulatorThread(Thread):
    _instance = None
    daemon = True

    @classmethod
    def instance(cls):
        if cls._instance is None:
            return None
        return cls._instance

    @classmethod
    def end(cls):
        if cls._instance:
            cls._instance.stop()
            cls._instance = None

    def __init__(self, parent, override_dll = None):
        self.__class__._instance = self
        Thread.__init__(self)
        self.loop: asyncio.AbstractEventLoop = None
        self._emu = DeSmuME(override_dll)
        self._thread_instance = None
        self.registered_main_loop = False
        self.parent = parent
        self._display_buffer = None

        self._fps_frame_count = 0
        self._fps_sec_start = 0
        self._fps = 0
        self._ticks_prev_frame = 0
        self._ticks_cur_frame = 0

    @property
    def emu(self):
        if THREAD_DEBUG and current_thread() != self._thread_instance:
            raise RuntimeError("The emulator may only be accessed from withing the emulator thread")
        return self._emu

    def start(self):
        start_lock.acquire()
        super().start()

    def run(self):
        self._thread_instance = current_thread()
        self._display_buffer = self.emu.display_buffer_as_rgbx()
        self.loop = asyncio.new_event_loop()
        nest_asyncio.apply(self.loop)
        asyncio.set_event_loop(self.loop)
        start_lock.release()
        try:
            self.loop.run_forever()
        except (KeyboardInterrupt, SystemExit):
            pass
        self.emu.destroy()

    def run_one_pending_task(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.loop.run_forever()

    def stop(self):
        start_lock.acquire()
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        start_lock.release()

    def register_main_loop(self):
        start_lock.acquire()
        if not self.registered_main_loop:
            self.loop.call_soon_threadsafe(self._emu_cycle)
            self.registered_main_loop = True
        start_lock.release()

    def run_task(self, coro) -> Future:
        """Runs an asynchronous task"""
        start_lock.acquire()
        retval = asyncio.run_coroutine_threadsafe(self.coro_runner(coro), self.loop)
        start_lock.release()
        return retval

    def load_controls(self, settings: DebuggerSettingsStore):
        """Loads the control configuration and returns it."""
        assert current_thread() == self._thread_instance

        default_keyboard, default_joystick = controls.load_default_config()
        configured_keyboard = settings.get_emulator_keyboard_cfg()
        configured_joystick = settings.get_emulator_joystick_cfg()

        kbcfg = configured_keyboard if configured_keyboard is not None else default_keyboard
        jscfg = configured_joystick if configured_joystick is not None else default_joystick

        for i, jskey in enumerate(jscfg):
            self.emu.input.joy_set_key(i, jskey)

        return kbcfg, jscfg

    def _emu_cycle(self):
        if not self.emu:
            self.registered_main_loop = False
            return False

        if self.emu.is_running():
            with fps_frame_count_lock:
                self._fps_frame_count += 1

                if not self._fps_sec_start:
                    self._fps_sec_start = self.emu.get_ticks()
                if self.emu.get_ticks() - self._fps_sec_start >= 1000:
                    self._fps_sec_start = self.emu.get_ticks()
                    self._fps = self._fps_frame_count
                    self._fps_frame_count = 0

            self.emu.cycle()

            self._ticks_cur_frame = self.emu.get_ticks()

            if self._ticks_cur_frame - self._ticks_prev_frame < TICKS_PER_FRAME:
                while self._ticks_cur_frame - self._ticks_prev_frame < TICKS_PER_FRAME:
                    self._ticks_cur_frame = self.emu.get_ticks()

            # TODO: This can be done better.
            ticks_to_wait = (1 / FRAMES_PER_SECOND) - (self._ticks_cur_frame - self._ticks_prev_frame - TICKS_PER_FRAME + 2) / 1000

            if ticks_to_wait < 0:
                ticks_to_wait = 0

            self._ticks_prev_frame = self.emu.get_ticks()

            self.loop.call_later(ticks_to_wait, self._emu_cycle)

            with display_buffer_lock:
                self._display_buffer = self.emu.display_buffer_as_rgbx()
            return True

        with display_buffer_lock:
            self._display_buffer = self.emu.display_buffer_as_rgbx()
        self.registered_main_loop = False
        return False

    @staticmethod
    async def coro_runner(coro):
        """Wrapper class to use ensure_future, to deal with uncaught exceptions..."""
        try:
            return await asyncio.ensure_future(coro)
        except BaseException as ex:
            # TODO Proper logging
            print(f"Uncaught EmulatorThread task exception:")
            print(''.join(traceback.format_exception(etype=type(ex), value=ex, tb=ex.__traceback__)))

    @synchronized(display_buffer_lock)
    def display_buffer_as_rgbx(self):
        return self._display_buffer

    @property
    @synchronized(fps_frame_count_lock)
    def current_frame_id(self):
        """The ID of the current frame. Warning: Resets every 1000 frames back to 0."""
        return self._fps_frame_count
