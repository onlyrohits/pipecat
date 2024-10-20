import os
import sys

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndFrame, LLMMessagesFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_response import (
    LLMAssistantResponseAggregator,
    LLMUserResponseAggregator,
)
from pipecat.services.cartesia import CartesiaTTSService
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)
from pipecat.serializers.twilio import TwilioFrameSerializer

from loguru import logger
import os

# from twilio.rest import Client
from dotenv import load_dotenv

import asyncio
from opensearchpy import OpenSearch
from concurrent.futures import ThreadPoolExecutor
import wave
import time
import io

# https://github.com/ddlBoJack/emotion2vec
class AudioChunks(FrameProcessor):
    """
    This class starts a talking animation when it receives an first AudioFrame,
    and then returns to a "quiet" sprite when it sees a TTSStoppedFrame.
    """

    def __init__(self):
        super().__init__()
        self._is_talking = False
        self._websocket_audio_buffer = bytes()

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, AudioRawFrame):
            if not self._is_talking:
                # await self.push_frame(talking_frame)
                self._is_talking = True
                print("Talking started *****")
                RECORD_SECONDS = 3
                WAVE_OUTPUT_FILENAME = f"user_audio_{int(time.time())}.wav"

                frame = AudioRawFrame(
                            audio=self._websocket_audio_buffer[:6400], # 200ms of audio
                            sample_rate=16000,
                            num_channels=1
                        )
                
                buffer = io.BytesIO()
                start_time = time.time()
                frames_recorded = 0
                frames_needed = int(RECORD_SECONDS * SAMPLE_RATE)
                
                while frames_recorded < frames_needed:
                    buffer.write(frame.audio)
                    frames_recorded += len(frame.audio) // 2  # Assuming 16-bit audio
                    if time.time() - start_time >= RECORD_SECONDS:
                        break
                
                buffer.seek(0)
                
                with open(WAVE_OUTPUT_FILENAME, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)  # Assuming 16-bit audio
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(buffer.read())

        # elif isinstance(frame, TTSStoppedFrame):
        #     await self.push_frame(quiet_frame)
        #     self._is_talking = False

        await self.push_frame(frame)


        # if isinstance(frame, AudioRawFrame):
        #     frame: AudioRawFrame
        #     if not self._is_talking:
        #         print(frame.audio)
                
        #         # save this audio bytes frame.audio to file
        #         import wave
        #         import time
        #         import io

        #         RECORD_SECONDS = 3
        #         SAMPLE_RATE = 16000  # Assuming 8kHz sample rate
        #         WAVE_OUTPUT_FILENAME = f"user_audio_{int(time.time())}.wav"
                
        #         buffer = io.BytesIO()
        #         start_time = time.time()
                
        #         while time.time() - start_time < RECORD_SECONDS:
        #             buffer.write(frame.audio)
        #             # Simulate waiting for next frame
        #             # time.sleep(0.02)  # Adjust this value based on your frame rate
                
        #         buffer.seek(0)
                
        #         with wave.open(WAVE_OUTPUT_FILENAME, 'wb') as wf:
        #             wf.setnchannels(1)
        #             wf.setsampwidth(2)  # Assuming 16-bit audio
        #             wf.setframerate(SAMPLE_RATE)
        #             wf.writeframes(buffer.read())

        #         print(f"Saved {RECORD_SECONDS} seconds of audio to {WAVE_OUTPUT_FILENAME}")


        #         # save this audio bytes frame.audio to file
                

        #         await self.push_frame(frame)
        #         self._is_talking = True
        # # frame
        # await self.push_frame(frame)


tools = [
        # {
        #     "type": "function",
        #     "function": {
        #         "name": "general_queries",
        #         "description": "Use this for query apart from change of address",
        #         "parameters": {
        #             "type": "object",
        #             "properties": {
        #                 "query": {
        #                     "type": "string",
        #                     "description": "general query",
        #                 }
        #             },
        #             "required": ["query"],
        #         },
        #     },
        # },
        
        {
            "type": "function",
            "function": {
                "name": "answer_user_question",
                "description": "Answer users question",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_question": {
                            "type": "string",
                            "description": "product query, rate of interest, change address, etc",
                        }
                    },
                    "required": ["user_question"],
                },
            },
        },
        # {
        #     "type": "function",
        #     "function": {
        #         "name": "change_address",
        #         "description": "Use it when user wants to change address",
        #         "parameters": {
        #                 "type": "object",
        #                 "properties": {
        #                 "user_question": {
        #                         "type": "string",
        #                         "description": "Use it when user wants to change address",
        #                     }
        #                 },
        #                 "required": ["user_question"],
        #             },
        #     },
        # },
        {
            "type": "function",
                "function": {
                    "name": "handle_residential_address",
                    "description": """Use it when the user expresses a desire to change their residential address. Explain the user about the process of changing residential address

                    To update your residential address, 
                    please send us a copy of the following documents (dated within the last 3 months) through the GXS Bank app, 
                    Help Centre: Contact Us form Utilities / telecommunication bill or Bank / credit card statement or Government correspondences or NRIC Your request will be processed within 2 working days upon receipt of your documents.""",
                    "parameters": {
                        "type": "object",
                        "properties": {
                        "user_question": {
                                "type": "string",
                                "description": "User statement about changing residential address",
                            }
                        },
                        "required": ["user_question"],
                    },
                },
        },
        {
            "type": "function",
                "function": {
                    "name": "handle_mailing_address",
                    "description": """Use it when the user expresses a desire to change their mailing address.  Explain the user about the process of changing mailing address

                    To update your mailing address: 
                        On homepage of the GXS Bank app, 
                        click on 'Me' tab on bottom right. 
                        Select 'Edit Profile' and click on edit icon for 'Mailing Address'. 
                        You will be prompted to verify your identity through biometrics (e.g. Touch or Face ID) or passcode. 
                        Key in your new mailing address and save to complete the update. """,
                    "parameters": {
                        "type": "object",
                        "properties": {
                        "user_question": {
                                "type": "string",
                                "description": "User statement about changing mailing address",
                            }
                        },
                        "required": ["user_question"],
                    },
                },
        },
        ChatCompletionToolParam(
                    type="function",
                    function={
                        "name": "transfer_call",
                        "description": "Transfer the current call to a human agent",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "call_sid": {
                                    "type": "string",
                                    "description": "The unique identifier for the current call",
                                },
                            },
                            "required": ["call_sid"],
                        },
                    },
                ),
       ]

# Initialize the OpenSearch client
def get_opensearch_client():
    client = OpenSearch(
        hosts=[
            {
                "host": "search-rapida-search-01-5k7cwwoptncgdagfvbqer7j3g4.aos.ap-south-1.on.aws",
                "port": 443,
            }
        ],
        http_auth=("rapida_username", "BigBang_rapida_2023"),
        scheme="https",
        use_ssl=True,
        verify_certs=True,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )
    return client


# Sync function to search OpenSearch
def search_opensearch(client, index, query):
    response = client.search(index=index, body=query)
    return response


# Async wrapper for the sync function
async def async_search_opensearch(client, index, query):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        response = await loop.run_in_executor(
            pool, search_opensearch, client, index, query
        )
    return response


# Function to take a string and get the list of matching text values
async def search_string(match_string):
    client = get_opensearch_client()
    index = "prod__vs__2001910341885231104__2001910393013796864__2103925666050211840__87967168452493312"

    # Define the query to match the given string
    query = {"size": 10, "query": {"match": {"text": match_string}}}

    # Perform the async search
    response = await async_search_opensearch(client, index, query)

    # Extract the text field values from the search hits
    text_values = [hit["_source"]["text"] for hit in response["hits"]["hits"]]

    logger.success(f"length results for :" + str(len(text_values)))
    return " \n ".join(text_values)


async def change_address(
        function_name, tool_call_id, args, llm: OpenAILLMService,
        context: OpenAILLMContext, result_callback
):
    logger.info(f"function_name={function_name}")
    
    result = {
                            "intention": "change_address",
                        }

    await result_callback(json.dumps(result))


async def transfer_call(function_name, tool_call_id, arguments, llm, context, result_callback):
    call_sid = arguments.get("call_sid")

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    client = Client(account_sid, auth_token)

    logger.debug(f"Transferring call {call_sid}")

    try:
        client.calls(call_sid).update(
            twiml=f'<Response><Dial>{os.getenv("TRANSFER_NUMBER")}</Dial></Response>'
        )
        result = "The call was transferred successfully, say goodbye to the customer."
        await result_callback(json.dumps({"success": result}))
    except Exception as error:
        logger.error(f"Error transferring call: {str(error)}")
        await result_callback(json.dumps({"error": str(error)}))

# async def change_adress_determine_type(function_name,
#                                        tool_call_id, args, llm: OpenAILLMService,
#                                        context: OpenAILLMContext, result_callback):
#     address_type = args["address_type"]
#     logger.info(f"function_name={function_name} and args={address_type}")

#     if args["address_type"] == "mailing":
#         context.set_tools(tool_to_process_address_change)
#         context.add_message(
#             {
#                 "role": "system",
#                 "content": """Explain the user about the process of changing mailing address
#                 To update your mailing address: 
#                     On homepage of the GXS Bank app, 
#                     click on 'Me' tab on bottom right. 
#                     Select 'Edit Profile' and click on edit icon for 'Mailing Address'. 
#                     You will be prompted to verify your identity through biometrics (e.g. Touch or Face ID) or passcode. 
#                     Key in your new mailing address and save to complete the update. 

#                 """,
#             }
#         )
#     else:
#         context.set_tools(tool_to_process_address_change)
#         context.add_message(
#             {
#                 "role": "system",
#                 "content": """Explain the user about the process of changing residential address

#                 To update your residential address, 
#                 please send us a copy of the following documents (dated within the last 3 months) through the GXS Bank app, 
#                 Help Centre: Contact Us form Utilities / telecommunication bill or Bank / credit card statement or Government correspondences or NRIC Your request will be processed within 2 working days upon receipt of your documents.

#                 """,
#             }
#         )
#     await llm.process_frame(OpenAILLMContextFrame(context), FrameDirection.DOWNSTREAM)




async def handle_residential_address(function_name,
                                       tool_call_id, args, llm: OpenAILLMService,
                                       context: OpenAILLMContext, result_callback):
    logger.info(f"function_name={function_name}")    
    # await result_callback("You request for residential address creation is successfull.")

    # context.add_message({
    #     "role": "system",
    #     "content": "The residential address change process has been explained. Ask the user if they need any further assistance."
    # })
    # context.set_tools(tools)  # Reset to original tools

    # await llm.process_frame(OpenAILLMContextFrame(context), FrameDirection.DOWNSTREAM)
    result = {
                            "intention": "change_residential_address",
                        }

    await result_callback(json.dumps(result))



async def handle_mailing_address(function_name,
                                    tool_call_id, args, llm: OpenAILLMService,
                                    context: OpenAILLMContext, result_callback):
    logger.info(f"function_name={function_name}")    
    # context.add_message({
    #     "role": "system",
    #     "content": "The mailing address change process has been explained. Ask the user if they need any further assistance."
    # })
    # context.set_tools(tools)  # Reset to original tools
    # await llm.process_frame(OpenAILLMContextFrame(context), FrameDirection.DOWNSTREAM)

    result = {
                            "intention": "change_mailing_address",
                        }

    await result_callback(json.dumps(result))


#
# Context retrival is happening
#
#
load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

import json
    


async def answer_user_question(
    function_name, tool_call_id, args, llm, context: OpenAILLMContext, result_callback
):
    logger.info(f"function_name={function_name}")
    ctx_str = await search_string(args["user_question"])

    query = args["user_question"]
    logger.info(f"function_name={function_name}, context={ctx_str}, query={query}")

    result = {
                "question": query,
                "response": ctx_str,
                "instructions":""
            }

    await result_callback(json.dumps(result))

    # await result_callback("Have given the information to the customer")
    


async def run_bot(websocket_client, stream_sid):
    transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
            serializer=TwilioFrameSerializer(stream_sid),
        ),
    )
    llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o")

    # registering the change address
    # llm.register_function(
    #     "change_address",
    #     change_address,
    # )

    llm.register_function("answer_user_question", answer_user_question)
    # llm.register_function("change_address", change_address)
    llm.register_function("handle_residential_address", handle_residential_address)
    llm.register_function("handle_mailing_address", handle_mailing_address)
    llm.register_function("transfer_call", transfer_call)

   


    # # tools define
    # tools = [
    #     {
    #         "type": "function",
    #         "function": {
    #             "name": "general_queries",
    #             "description": "Use this for general queries",
    #             "parameters": {
    #                 "type": "object",
    #                 "properties": {
    #                     "query": {
    #                         "type": "string",
    #                         "description": "general query",
    #                     }
    #                 },
    #                 "required": ["query"],
    #             },
    #         },
    #     },
    #     {
    #         "type": "function",
    #         "function": {
    #             "name": "change_address",
    #             "description": "Use it when user wants to change address",
    #         },
    #     },
    # ]

   

    messages = [
        {
            "role": "system",
            "content": os.getenv("PROMPT"),
        },
    ]

    #

    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"), sentiment=True)

    # tts = DeepgramTTSService(api_key=os.getenv("DEEPGRAM_API_KEY"))
    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id="79a125e8-cd45-4c13-8a67-188112f4dd22",  # British Lady
    )

    context = OpenAILLMContext(
        messages,
        tools,
    )

    from local_audio_save import LocalAudioSaverService
    
    ac = AudioChunks()
    audio_buffer_processor = AudioBufferProcessor()
    locao_audio_save_service = LocalAudioSaverService(
            audio_buffer_processor=audio_buffer_processor,
            call_id='abcd'
        )
    
    # context = OpenAILLMContext(messages)
    # context_aggregator = llm.create_context_aggregator(context)
    context_aggregator = llm.create_context_aggregator(context)
    pipeline = Pipeline(
        [
            transport.input(),
            # ac,
            stt,  # Speech-To-Text
            context_aggregator.user(),  # Context aggregator
            # context_aggregator.user(),
            llm,  # LLM
            tts,  # Text-To-Speech
            audio_buffer_processor,
            locao_audio_save_service,
            transport.output(),  # Websocket output to client
            context_aggregator.assistant(),
            # context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))

    #
    #
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):

        print(client)
        # Kick off the conversation.
        messages.append(
            {"role": "system", "content": "Please introduce yourself to the user."}
        )
        await task.queue_frames([LLMMessagesFrame(messages)])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await task.queue_frames([EndFrame()])

    runner = PipelineRunner(handle_sigint=False)

    await runner.run(task)