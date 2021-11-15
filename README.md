# Coqui-STT-Websocket-Streaming

This directory contains a service that can receive audio data over websocket and sends the 
transcription result using CoquiSTT speech-to-text-engine back to the client. This service
can also receive RTP packets and extract the payload (transcription of payload is work in progress).
The websocket server code in this project is a modified version of [this GitHub project](https://github.com/coqui-ai/STT-examples/tree/r1.0/python_websocket_server).

## Configuration

Server configuration is specified in the [`application.conf`](application.conf) file.

## Usage

### Starting the server

1. Git clone the repository
2. Download and install [ffmpeg](https://www.ffmpeg.org/download.html)
3. Download the [acoustic model](https://github.com/coqui-ai/STT-models/releases/download/english/coqui/v0.9.3/model.tflite) and [language model](https://github.com/coqui-ai/STT-models/releases/download/english/coqui/v0.9.3/coqui-stt-0.9.3-models.scorer) files for CoquiSTT and place it in the cloned repository
4. Create a venv using python -m venv venv
5. Enter venv using venv\scripts\activate (Windows) or source venv/bin/activate (Linux)
6. Run pip install -r requirements.txt
7. Run python -m coqui_server.app

### Sending requests to server

#### Websocket

A sample client script is provided, which can be run by executing the following:

```
coqui_server\client.py 2830-3980-0043.wav
```

`2830-3980-0043.wav` can be replaced with a path to the audio file to be transcribed.

The websocket client-server request-response process looks like the following:

1. Client opens websocket _W_ to server
2. Client sends _binary_ audio data via _W_
3. Server responds with transcribed text via _W_ once transcription process is completed. The server's response is 
   in JSON format
4. Server closes _W_

The time _t_ taken by the transcription process depends on several factors, such as the duration of the audio, how busy
the service is, etc. Under normal circumstances, _t_ is roughly the same as the duration of the provided audio.

Because this service uses websockets, it is currently not possible to interact with it using certain HTTP clients
which do not support websockets, like `curl`.

#### RTP

The server can also accept RTP packets. Upon receiving RTP packets, the server decodes the RTP packet to obtain the payload.
The payload is then sent to `webrtcvad`(https://pypi.org/project/webrtcvad/), and the voiced audio frames are sent to
CoquiSTT for transcription. The transcription functionality is still work in progress.