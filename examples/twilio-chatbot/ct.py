from cartesia import Cartesia
import pyaudio
import os

client = Cartesia(api_key="be665b89-7eec-4926-8197-d0f18fb2acd8")
voice_name = "Barbershop Man"
voice_id = "a0e99841-438c-4a64-b679-ae501e7d6091"
voice = client.voices.get(id=voice_id)

transcript = "Hello! Welcome to Cartesia"

# You can check out our models at https://docs.cartesia.ai/getting-started/available-models
model_id = "sonic-english"

# You can find the supported `output_format`s at https://docs.cartesia.ai/reference/api-reference/rest/stream-speech-server-sent-events
output_format = {
    "container": "raw",
    "encoding": "pcm_f32le",
    "sample_rate": 44100,
}

p = pyaudio.PyAudio()
rate = 44100

stream = None

# Generate and stream audio
for output in client.tts.sse(
    model_id=model_id,
    transcript=transcript,
    voice_embedding=voice["embedding"],
    stream=True,
    output_format=output_format,
):
    buffer = output["audio"]

    if not stream:
        stream = p.open(format=pyaudio.paFloat32, channels=1, rate=rate, output=True)

    # Write the audio data to the stream
    stream.write(buffer)

stream.stop_stream()
stream.close()
p.terminate()
