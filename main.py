from asyncio.log import logger
import whisper
import os
import requests
import pika
import json
from typing import Iterator, List, TextIO
import logging

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger()


connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='host.docker.internal'))

channel = connection.channel()

channel.queue_declare(queue='rpc_queue')

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
    mel = whisper.log_mel_spectrogram(audio).to("cpu")

    # detect the spoken language
    _, probs = model.detect_language(mel)
    detected_language = max(probs, key=probs.get)

    return detected_language, probs

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
        count +=1
        srt.extend([f"{count}\n", f"{srt_format_timestamp(segment['start'])} --> {srt_format_timestamp(segment['end'])}\n", f"{segment['text'].replace('-->', '->').strip()}\n\n"])
    
    return srt




def on_request(ch, method, props, body) -> None:
    
    options = json.loads(body)

    try:
        if not options["model"] in ["small", "medium", "large"]:
            response = {"error": "invalid model"}
            ch.basic_publish(
                exchange='',
                routing_key=props.reply_to,
                properties=pika.BasicProperties(correlation_id = \
                                                    props.correlation_id),
                body=json.dumps(response)
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)


        # FOR PROD assert file exists in bucket
        elif options["audio"]:
            try: 
                logger.info(requests.get(options["audio"]))
                logger.info(requests.get(options["audio"]).headers.get("content-type"))

                logger.info(requests.get(options["audio"]).headers.get("content-type") == "audio/mpeg")
                
            except:
                response = {"error": "invalid audio file"}
                ch.basic_publish(
                    exchange='',
                    routing_key=props.reply_to,
                    properties=pika.BasicProperties(correlation_id = \
                                                        props.correlation_id),
                    body=json.dumps(response)
                )
                ch.basic_ack(delivery_tag=method.delivery_tag)

        elif not options["language"] in ["auto", "en", "es", "fr", "de", "it", "pt", "ru"]:
            response = {"error": "invalid language"}
            ch.basic_publish(
                exchange='',
                routing_key=props.reply_to,
                properties=pika.BasicProperties(correlation_id = \
                                                    props.correlation_id),
                body=json.dumps(response)
            )
            ch.basic_ack(delivery_tag=method.delivery_tag)

    finally:
        logger.info("all good")
        response = {
            "status": "working",
        }

        # get audio file
        with open("audio.mp3", "wb") as f:
            f.write(requests.get(options["audio"]).content)
        audio = "audio.mp3"
        logger.info("got audio file")
        model = whisper.load_model(options["model"])
        logger.info("loaded model")
        # detect the language if not specified
        detected_language = None
        if options["language"] == "auto":
            logger.info("Detecting language...")
            detected_language, _ = detect_language(model, audio)
            logger.info(f"Detected language: {detected_language}")

        else:
            language = options["language"]
            logger.info(f"Language: {language}")

        logger.info("Transcribing audio...")
        result = model.transcribe(audio, verbose=True, language=[detected_language if detected_language else options["language"]][0])
        logger.info("Transcribed audio")

        logger.info("Writing SRT file...")
        srt = write_srt(result["segments"])
        logger.info("Wrote SRT file")


        response = {
            "status": "success",
            "language": [detected_language if detected_language else options["language"]][0],
            "srt": srt,
        }

        ch.basic_publish(
            exchange='',
            routing_key=props.reply_to,
            properties=pika.BasicProperties(correlation_id = \
                                                props.correlation_id),
            body=json.dumps(response)
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)

        # delete audio file
        logger.info("Deleting audio file")
        os.remove("audio.mp3")
        logger.info("Deleted audio file")

        logger.info(" [x] Done")
        logger.info(" [x] Awaiting RPC requests")


channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue='rpc_queue', on_message_callback=on_request)

logger.info(" [x] Awaiting RPC requests")
channel.start_consuming()
