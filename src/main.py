import functools
import json
import logging
import os
import time
import threading 
from typing import Iterator, List
import pika
import requests
import whisper
from torch.cuda import is_available as cuda_is_available

DEVICE = "cuda" if cuda_is_available() else "cpu"

lock = threading.Lock()
message = {"status":"None"}

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
LOGGER = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

def srt_format_timestamp(seconds: float) -> str:
    assert seconds >= 0, "non-negative timestamp expected"
    milliseconds = round(seconds * 1000.0)

    hours = milliseconds // 3_600_000
    milliseconds -= hours * 3_600_000

    minutes = milliseconds // 60_000
    milliseconds -= minutes * 60_000

    seconds = milliseconds // 1_000
    milliseconds -= seconds * 1_000

    return (f"{hours}:") + f"{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def write_srt(transcript: Iterator[dict]) -> List:
    count = 0
    srt = []
    for segment in transcript:
        count += 1
        srt.extend(
            [
                f"{count}",
                f"{srt_format_timestamp(segment['start'])} --> {srt_format_timestamp(segment['end'])}",
                f"{segment['text'].replace('-->', '->').strip()}",
            ]
        )

    with open("output.srt", "w") as f:
        for line in srt:
            f.write(f"{line}")
        from fire import upload_srt
        import random
        upload_srt(f, f"output{random.randint(1,1000)}.srt")
    return srt

def detect_language(model, audio):
    """Detect the language of the audio.

    Args:
        audio: audio waveform with shape (1, audio_length)

    Returns:
        detected language and a dictionary of probabilities for each language
    """
    audio = whisper.load_audio(audio)
    audio = whisper.pad_or_trim(audio)

    # make log-Mel spectrogram and move to the same device as the model
    mel = whisper.log_mel_spectrogram(audio).to(DEVICE)

    # detect the spoken language
    _, probs = model.detect_language(mel)
    detected_language = max(probs, key=probs.get)

    return detected_language, probs

def ack_message(channel, delivery_tag):
    """Note that `channel` must be the same pika channel instance via which
    the message being ACKed was retrieved (AMQP protocol constraint).
    """
    if channel.is_open:
        channel.basic_ack(delivery_tag)
    else:
        # Channel is already closed, so we can't ACK this message;
        # log and/or do something that makes sense for your app in this case.
        pass

def do_work(connection, channel, delivery_tag, body):
    thread_id = threading.get_ident()
    fmt1 = 'Thread id: {} Delivery tag: {} Message body: {}'
    LOGGER.info(fmt1.format(thread_id, delivery_tag, body))
    
    # check the body is json
    try:
        body = json.loads(body)
        LOGGER.info('body is json')
    except:
        LOGGER.warning('body is not json')
        exit(1)

    from test import check_params

    respone = check_params(body)
    
    if respone.get('status') == 'success':
        LOGGER.info(f"Params are valid, {respone.get('message')}")

        with open("audio.mp3", "wb") as f:
            f.write(requests.get(body["audio_url"]).content)
            audio = f.name
        LOGGER.info("Audio file downloaded")

        if body["model_size"] == "large-v2":
            LOGGER.info(f"Loading large model... Using device: {DEVICE}")
            model = whisper.load_model("medium", device=DEVICE)
        else:
            model = whisper.load_model(body["model_size"], device=DEVICE)
        LOGGER.info("Model loaded")

        detected_language = None
        if body["video_language"] == "auto":
            LOGGER.info("Detecting language...")
            detected_language, _ = detect_language(model, audio)
            LOGGER.info(f"Detected language: {detected_language}")
        else:
            language = body["video_language"]
            LOGGER.info(f"Language: {language}")
        
        transcription = model.transcribe(
            audio,
            verbose=True,
            language=[detected_language if detected_language else body["video_language"]][
                0
            ],
        )
        LOGGER.info("Transcribed audio")

        srt = write_srt(transcription["segments"])
        LOGGER.info("Wrote SRT file")
        
        transcription_response = {
            "status": "success",
            "language": detected_language if detected_language else body["video_language"],
            "srt": srt,
        }

        os.remove("audio.mp3")
        LOGGER.info("Deleted audio file")

        print("Transcription completed successfully, ", transcription_response)
        
    elif respone.get('status') == 'error':
        LOGGER.warning(f"Params are invalid, {respone.get('message')}")
        exit(1)
    else:
        LOGGER.warning('Unknown error in check params')
        
    # do long running task
    time.sleep(1)

    cb = functools.partial(ack_message, channel, delivery_tag)
    connection.add_callback_threadsafe(cb)

def on_message(channel, method_frame, header_frame, body, args):
    (connection, threads) = args
    delivery_tag = method_frame.delivery_tag
    t = threading.Thread(target=do_work, args=(connection, channel, delivery_tag, body))
    t.start()
    threads.append(t)



def queue_get_task():
    credentials = pika.PlainCredentials('test-client', '?cd#6CzQn3@JdT?t')
    parameters = pika.ConnectionParameters(host='34.173.243.142',
                                               port=5672,
                                               virtual_host='test-client',
                                               credentials=credentials,
                                               heartbeat=1)
    
    connection = pika.BlockingConnection(parameters)
    
    channel = connection.channel()
    channel.exchange_declare(exchange="test_exchange", exchange_type="direct", passive=False, durable=True, auto_delete=False)
    channel.queue_declare(queue="hello", auto_delete=False)
    channel.queue_bind(queue='hello', exchange="test_exchange", routing_key="standard_key")
    # Note: prefetch is set to 1 here as an example only and to keep the number of threads created
    # to a reasonable amount. In production you will want to test with different prefetch values
    # to find which one provides the best performance and usability for your solution
    channel.basic_qos(prefetch_count=1)

    threads = []
    on_message_callback = functools.partial(on_message, args=(connection, threads))
    channel.basic_consume(queue="hello", on_message_callback=on_message_callback)

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()

    # Wait for all to complete
    for thread in threads:
        thread.join()

    connection.close()



queue_get_task()


