#
# Copyright (c) 2024, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import asyncio
import aiohttp
import os
import json
import sys

from pipecat.frames.frames import LLMMessagesFrame, Frame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.llm_response import (
    LLMAssistantContextAggregator,
    LLMUserContextAggregator,
)
from pipecat.services.openai import OpenAILLMContextFrame, OpenAILLMContext
from pipecat.processors.logger import FrameLogger
from pipecat.services.elevenlabs import ElevenLabsTTSService
from pipecat.services.openai import OpenAILLMService
from pipecat.transports.services.daily import DailyParams, DailyTransport
from pipecat.vad.silero import SileroVADAnalyzer
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionFunctionMessageParam,
    ChatCompletionToolParam,
    ChatCompletionUserMessageParam,
)
from pipecat.frames.frames import (
    LLMFullResponseStartFrame,
    LLMFullResponseEndFrame,
    LLMResponseEndFrame,
    LLMResponseStartFrame,
    LLMFunctionCallFrame,
    LLMFunctionStartFrame,
    TextFrame
)

from runner import configure

from loguru import logger

from dotenv import load_dotenv
load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


class FunctionCaller(FrameProcessor):
    def __init__(self, context):
        self._context = context
        super().__init__()

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # When we receive function call frames, we need to ask the LLM to run a completion
        # again so it actually talks to the user
        if isinstance(frame, LLMFunctionCallFrame):
            tool_call = ChatCompletionFunctionMessageParam({
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": frame.tool_call_id,
                        "function": {
                            "arguments": frame.arguments,
                            "name": frame.function_name
                        },
                        "type": "function"
                    }
                ]

            })
            self._context.add_message(tool_call)

            # This is where you'd actually call the function
            weather_result = {
                "city": "San Francisco, CA",
                "conditions": "Sunny and beautiful",
                "temperature": "75 degrees Fahrenheit"
            }
            print(f"weather_result: {weather_result}")
            result = ChatCompletionToolParam({
                "tool_call_id": frame.tool_call_id,
                "role": "tool",
                "content": json.dumps(weather_result)
            })
            print(f"result: {result}")
            try:
                self._context.add_message(result)
            except Exception as e:
                print(f"got exception: {e}")
            print(f"context now includes: {self._context.messages}")
            await self.push_frame(OpenAILLMContextFrame(self._context), FrameDirection.UPSTREAM)
        else:
            print(f"!!! Got a frame I'm forwarding: {frame}")
            await self.push_frame(frame)


async def main(room_url: str, token):
    async with aiohttp.ClientSession() as session:
        transport = DailyTransport(
            room_url,
            token,
            "Respond bot",
            DailyParams(
                audio_out_enabled=True,
                transcription_enabled=True,
                vad_enabled=True,
                vad_analyzer=SileroVADAnalyzer()
            )
        )

        tts = ElevenLabsTTSService(
            aiohttp_session=session,
            api_key=os.getenv("ELEVENLABS_API_KEY"),
            voice_id=os.getenv("ELEVENLABS_VOICE_ID"),
        )

        llm = OpenAILLMService(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4-turbo-preview")

        fl_in = FrameLogger("Inner")
        fl_out = FrameLogger("Outer")

        tools = [
            ChatCompletionToolParam(
                type="function",
                function={
                    "name": "get_current_weather",
                    "description": "Get the current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA",
                            },
                            "format": {
                                "type": "string",
                                "enum": [
                                    "celsius",
                                    "fahrenheit"],
                                "description": "The temperature unit to use. Infer this from the users location.",
                            },
                        },
                        "required": [
                            "location",
                            "format"],
                    },
                })]
        messages = [
            {
                "role": "system",
                "content": "You are a helpful LLM in a WebRTC call. Your goal is to demonstrate your capabilities in a succinct way. Your output will be converted to audio so don't include special characters in your answers. Respond to what the user said in a creative and helpful way.",
            },
        ]

        context = OpenAILLMContext(messages, tools)
        tma_in = LLMUserContextAggregator(context)
        tma_out = LLMAssistantContextAggregator(context)
        caller = FunctionCaller(context)
        pipeline = Pipeline([
            fl_in,
            transport.input(),
            tma_in,
            llm,
            caller,
            fl_out,
            tts,
            transport.output(),
            tma_out
        ])

        task = PipelineTask(pipeline)

        @ transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            transport.capture_participant_transcription(participant["id"])
            # Kick off the conversation.
            await tts.say("Hi! Ask me about the weather in San Francisco.")

        runner = PipelineRunner()

        await runner.run(task)


if __name__ == "__main__":
    (url, token) = configure()
    asyncio.run(main(url, token))
