import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter

from pyhocon import ConfigFactory
from sanic import Sanic, response
from sanic.log import logger

from .engine import SpeechToTextEngine
from .models import Error, Response

# Load app configs and initialize Coqui model
conf = ConfigFactory.parse_file("application.conf")
engine = SpeechToTextEngine(
    model_path=Path(conf["coqui.model"]).absolute().as_posix(),
    scorer_path=Path(conf["coqui.scorer"]).absolute().as_posix(),
)

# Initialze Sanic, ThreadPoolExecutor and set maximum websocket size
executor = ThreadPoolExecutor(max_workers=conf["server.threadpool.count"])
app = Sanic("coqui_server")
app.config.WEBSOCKET_MAX_SIZE = conf["server.websocket.max_size"]


@app.route("/", methods=["GET"])
async def healthcheck(_):
    return response.text("Welcome to CoquiSTT Server!")


@app.websocket("/api/v1/stt")
async def stt(request, ws):
    logger.debug(f"Received {request.method} request at {request.path}")
    try:
        audio = await ws.recv()

        inference_start = perf_counter()
        text = await app.loop.run_in_executor(executor, lambda: engine.run_wav(audio))
        inference_end = perf_counter() - inference_start

        await ws.send(json.dumps(Response(text, inference_end).__dict__))
        logger.debug(
            f"Completed {request.method} request at {request.path} in {inference_end} seconds"
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.debug(
            f"Failed to process {request.method} request at {request.path}. The exception is: {str(e)}."
        )
        await ws.send(json.dumps(Error("Something went wrong").__dict__))

    await ws.close()


class RtpServerProtocol:
    """Protocol to process received RTP packets"""

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        # logger.debug(f"RTP packet received from {addr}")
        app.add_task(engine.process_rtp_packet(data))


# Create a datagram socket and listen for incoming datagrams
@app.before_server_start
async def setup_udp(app, loop):
    print("UDP server up and running")
    print("Server listening on port", conf["server.http.port"])
    transport, protocol = await app.loop.create_datagram_endpoint(
        lambda: RtpServerProtocol(),
        local_addr=(conf["server.http.host"], conf["server.http.port"]),
    )


# Create and process queue of voiced audio frames
@app.after_server_start
async def start_transcribe_audio(app, loop):
    app.queue = asyncio.Queue()
    app.add_task(engine.transcribe_streaming_audio(app.queue))


if __name__ == "__main__":
    app.run(
        host=conf["server.http.host"],
        port=conf["server.http.port"],
        access_log=True,
        debug=True,
    )
