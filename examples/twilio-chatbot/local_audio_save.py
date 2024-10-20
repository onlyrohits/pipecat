import os
import uuid
from datetime import datetime
from typing import Dict

from pipecat.frames.frames import CancelFrame, StartFrame, EndFrame, Frame
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.ai_services import AIService

from loguru import logger

try:
    import aiofiles
    import aiofiles.os
except ModuleNotFoundError as e:
    logger.error(f"Exception: {e}")
    logger.error(
        "In order to use LocalAudioSaverService, you need to `pip install aiofiles`."
    )
    raise Exception(f"Missing module: {e}")


class LocalAudioSaverService(AIService):
    """Initialize a LocalAudioSaverService instance.

    This class uses an AudioBufferProcessor to get the conversation audio and
    saves it locally as a WAV file.

    Args:
        audio_buffer_processor (AudioBufferProcessor): The audio buffer processor to use.
        call_id (str): Your unique identifier for the call.
        output_dir (str, optional): Directory to save audio files. Defaults to "recordings".

    Attributes:
        call_id (str): Stores the unique call identifier.
        output_dir (str): Directory path for saving audio files.
    """

    def __init__(
        self,
        *,
        audio_buffer_processor: AudioBufferProcessor,
        call_id: str,
        output_dir: str = "recordings",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._audio_buffer_processor = audio_buffer_processor
        self._call_id = call_id
        self._output_dir = output_dir

    async def start(self, frame: StartFrame):
        pass

    async def stop(self, frame: EndFrame):
        await self._save_audio()

    async def cancel(self, frame: CancelFrame):
        await self._save_audio()

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        await self.push_frame(frame, direction)

    async def _save_audio(self):
        pipeline = self._audio_buffer_processor
        if pipeline.has_audio():
            os.makedirs(self._output_dir, exist_ok=True)
            filename = self._get_output_filename()
            wave_data = pipeline.merge_audio_buffers()

            try:
                async with aiofiles.open(filename, "wb") as file:
                    await file.write(wave_data)
                logger.info(f"Audio saved successfully: {filename}")
                pipeline.reset_audio_buffer()
            except Exception as e:
                logger.error(f"Failed to save audio: {e}")

    def _get_output_filename(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{self._output_dir}/{timestamp}-{self._call_id}-{uuid.uuid4().hex}.wav"

