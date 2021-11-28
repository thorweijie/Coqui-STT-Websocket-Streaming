import collections
import wave
from io import BytesIO


import ffmpeg
import numpy as np
from pyhocon import ConfigFactory
from rtp import RTP
from stt import Model
import webrtcvad

# Load default values for RTP packet processing
conf = ConfigFactory.parse_file("application.conf")

frame_duration = conf["audio.frame_duration"]
padding = conf["vad.padding"]
ratio = conf["vad.ratio"]
sample_rate = conf["audio.sample_rate"]


# Convert audio to 16kHz sampling rate, 16-bit bit depth and mono channel
def normalize_audio(audio):
    out, err = (
        ffmpeg.input("pipe:0")
        .output(
            "pipe:1",
            f="WAV",
            acodec="pcm_s16le",
            ac=1,
            ar="16k",
            loglevel="error",
            hide_banner=None,
        )
        .run(input=audio, capture_stdout=True, capture_stderr=True)
    )
    if err:
        raise Exception(err)
    return out


class SpeechToTextEngine:
    def __init__(self, model_path, scorer_path):
        numPaddingFrames = padding // frame_duration
        self.model = Model(model_path=model_path)
        self.model.enableExternalScorer(scorer_path=scorer_path)
        self.ring_buffer = collections.deque(maxlen=numPaddingFrames)
        self.triggered = False

        # Create VAD object with aggressiveness set to 3 (most aggressive)
        self.vad = webrtcvad.Vad(3)

    # Get payload from RTP packet and add voiced frames to queue
    async def process_rtp_packet(self, audio):
        decoded_payload = RTP().fromBytes(audio).payload

        is_speech = self.vad.is_speech(decoded_payload, sample_rate)

        if not self.triggered:
            self.ring_buffer.append((decoded_payload, is_speech))
            num_voiced = len([f for f, speech in self.ring_buffer if speech])
            if num_voiced > ratio * self.ring_buffer.maxlen:
                self.triggered = True
                for f, s in self.ring_buffer:
                    await self.frames_queue.put(f)
                self.ring_buffer.clear()
        else:
            await self.frames_queue.put(decoded_payload)
            self.ring_buffer.append((decoded_payload, is_speech))
            num_unvoiced = len([f for f, speech in self.ring_buffer if not speech])
            if num_unvoiced > ratio * self.ring_buffer.maxlen:
                self.triggered = False
                await self.frames_queue.put(None)
                self.ring_buffer.clear()

    def run_wav(self, audio):
        audio = normalize_audio(audio)
        audio = BytesIO(audio)
        with wave.open(audio) as wav:
            audio = np.frombuffer(wav.readframes(wav.getnframes()), np.int16)
        result = self.model.stt(audio_buffer=audio)
        return result

    # Get voiced frames from queue and stream to CoquiSTT
    async def transcribe_streaming_audio(self, queue):
        self.frames_queue = queue
        stream_context = self.model.createStream()
        print("Streaming interface opened")
        while True:
            frame = await self.frames_queue.get()
            print("streaming frame")
            if frame is not None:
                stream_context.feedAudioContent(np.frombuffer(frame, np.int16))
            else:
                print("end utterence")
                text = stream_context.finishStream()
                print("Recognized:", text)
                stream_context = self.model.createStream()
