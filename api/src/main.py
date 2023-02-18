# main.py

import json
import logging
import os
import time
from multiprocessing import AuthenticationError
from pathlib import Path
from sys import stdout
from typing import Any
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from settings import Dubbing_Settings, Order
from translate import translate
from user import USER
from utils import download_srt_file, srt_to_dict, tanslated_srt_to_file
from voice_synth import synthesize_text_azure_batch
load_dotenv()

logging.basicConfig(
    level=[10 if os.environ.get("DEBUG") == "True" else 20][0],
    format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s \n",
    datefmt="%d/%b/%Y %H:%M:%S",
    stream=stdout,
)

app = FastAPI()



# ----------------------#
#    BUISNESS LOGIC    #
# ----------------------#
def authorize(request: Request) -> USER:
    logging.debug("AUTHORIZING")
    auth_headers = request.headers.get("authorization")
    logging.debug(f"AUTH HEADERS: {auth_headers}")
    assert auth_headers != None, "AUTHORIZATION ERROR: No Authorization Header"

    try:
        logging.debug("CREATING USER")
        return USER(auth_headers.replace("Bearer ", ""))

    except Exception as e:
        raise AuthenticationError(str(e))

def get_main_srt_file(user: USER, order: dict):
    """
    Downloads main srt file from storage and converts it to the subs dict

    Parameters
    ----------
    user (USER):
        User object
    order (dict):
        Order info

    Returns
    -------
    dict:
        Subs dict

    Raises
    ------
    Exception:
        Error downloading srt file
    """
    assert order.get("main_srt") != None and type(order.get("main_srt")) == str and order.get("main_srt") != "", f"main_srt: {order.get('main_srt')}"

    assert type(order.get("dubbing_settings")) == dict, f"dubbing_settings: {order.get('dubbing_settings')}"
    
    id = order.get("main_srt").split("/")[-2] # type: ignore

    # download main srt
    logging.debug(f"CREATING DOWNLOAD URL. PATH: {order.get('main_srt')}")
    main_srt_url = user.create_download_url(path=order.get("main_srt"))

    with requests.get(main_srt_url, stream=True) as r:
        r.raise_for_status()
        r.content.decode("utf-8")
        lines = r.content.decode("utf-8").split("\n")
        subs_dict = srt_to_dict(
            lines, order['dubbing_settings'].get("add_line_buffer_milliseconds")
        )

    return subs_dict

def to_subs_dict(file: Path, order: dict) -> dict:

    dubbing_settings = order["dubbing_settings"]
    logging.debug(f"DUBBING SETTINGS: {dubbing_settings}")
    assert (
        dubbing_settings.get("add_line_buffer_milliseconds") != None
    ), "No add_line_buffer_milliseconds"

    with open(file, "r") as f:
        lines = f.readlines()
        
        logging.debug(f"SUBS LINES READ. LEN: {len(lines)}")
        
        subs_dict = srt_to_dict(
            lines, dubbing_settings.get("add_line_buffer_milliseconds")
        )
        return subs_dict

def run_translate(
    dubbing_instance: dict, data: Order, user: USER, subs_dict: dict
)  -> dict[str, Any]:
    """Runs translation and uploads to storage
    
    Parameters
    ----------
    dubbing_instance (dict):
        Dubbing instance
    data (Order):
        Order data
    user (USER):
        User object
    subs_dict (dict):
        Subtitles dict
    
    Returns
    -------
    dict[str, str]:
        {
            "order_id": data.order_id,
            "order_settings": data.settings.dict(),
            "dubbing_instance": dubbing_instance,
            "t_subs_dict": t_subs_dict,
        }

    """
    logging.debug(f"TRANSLATING: {dubbing_instance.get('translation_target_language')}")
    t_subs_dict = translate(
        subs_dict=subs_dict,
        target_language=dubbing_instance.get("translation_target_language"),  # type: ignore
        formality=dubbing_instance.get("formality_preference"),  # type: ignore
        combine_subtitles=dubbing_instance.get("combine_subtitles"),  # type: ignore
        combine_max_characters=dubbing_instance.get("combine_subtitles_max_chars"),  # type: ignore
    )

    logging.debug(
        f"UPLOADING TRANSLATED SRT TO DB: {dubbing_instance.get('translation_target_language')}"
    )

    out = {
        "order_id": data.order_id,
        "order_settings": data.settings.dict(),
        "dubbing_instance": dubbing_instance,
        "t_subs_dict": t_subs_dict,
    }

    user.upload_translation(
        file=json.dumps(out),
        order_id=data.order_id,
        language=dubbing_instance.get("translation_target_language"),
    )

    return out

def dubs(translated_subs: dict, user: USER, order_id: str):
    for lang, trans in translated_subs.items():
        order_settings = trans.get("order_settings")
        print(f"ORDER SETTINGS: {order_settings}")
        if order_settings.get("skip_synthesize") == True:
            logging.debug(f"SKIPPING SYNTHESIZE FOR: {lang}")
            continue
        lang_dict = trans.get("dubbing_instance")
        t_subs_dict = trans.get("t_subs_dict")

        print(f"TRANSLATED SUBS DICT , {order_settings}, {lang_dict}, {t_subs_dict}")

        upload_files, subs_dict = synthesize_text_azure_batch(
                    subs_dict=t_subs_dict,
                    lang_dict=lang_dict,
                    second_pass=False,
                    azure_sentence_pause=80,
                )
                
        
        user.upload_translated_audio(data=upload_files, order_id=order_id, language=lang)


def del_temp_files(id: str):
    logging.debug("DELETING TEMP FILES")
    if os.path.exists(f"temp/{id}"):
        os.system(f"rm -rf temp/{id}")




# @app.post("/test/dubs/")
# def test_dubs(request: Request, data: Order):
#     user = authorize(request)
#     user.initialize_db_order(order=data)
#     with open(r"C:\dev\projects\test-app\api\src\workingFolder\0001.mp3", "r") as f:
#         file = f.buffer.read()
#         file_name = f.name.split("/")[-1]
#         user.upload_translated_audio(data=file, order_id="Jyh9aWxS4o87ZtpMRoy3", language="ES", file_name=file_name)
#     return {"message": "ok"}




#----------------------#
#      ENDPOINTS       #
#----------------------#
@app.post("/translate/")
def translate_endpoint(request: Request, data: Order) -> Any:
    """Translate endpoint. Translates srt file and uploads to storage

    Flow:
        1. Authorize user
        2. TODO: Authorize order (stripe)
        3. Initialize order in db and storage
        4. Download srt from storage
        5. Convert srt to subs dict
        6. Translate
        7. Upload translation to storage
        8. Update order in db


    Parameters
    ----------
    request (Request):
        FastAPI request object
    data (Order):
        Order object

    Returns
    -------
    Any:
        Response

    TODO: Break into smaller functions,

    """

    try:
        logging.debug("AUTHORIZING")
        user = authorize(request)
    except AuthenticationError as e:
        return {"Authentication Error": str(e)}

    logging.debug("INITIALIZING DB ORDER")
    order = user.initialize_db_order(order=data)

    # download srt
    try:
        logging.debug("DOWNLOADING translation file")
        subs_dict = get_main_srt_file(user, order)
    except Exception as e:
        return {"Error getting translation file": str(e)}

    # run translate
    translated_subs = {}
    for i in order.get("dubbing_instances"):
        try:
            out = run_translate(
                dubbing_instance=i, 
                data=data, 
                user=user, 
                subs_dict=subs_dict)
            translated_subs[i.get("translation_target_language")] = out
        except Exception as e:
            return {"Error translating": str(e)}
    
    # if synthesize is true, synthesize
    # TODO: Synthesize

    print("TRANSLATED SUBS", translated_subs)

    dubs(translated_subs, user, order_id=data.order_id)

    return {"message": "success", "ordered": [i for i,j in translated_subs.items()]}


@app.get("/language_data/")
def get_language_codes():
    d = Dubbing_Settings()
    return {"message": "language codes", "MS codes": d.microsoft_languages_codes, "DEEPL codes": d.translation_target_language_codes, "voices": d.microsoft_languages_voices}


@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(f"{process_time:0.4f} sec")
    return response


@app.get("/test/")
def test(request: Request):
    # print(request.client)
    print("Hello")
    time.sleep(5)
    print("bye")
    return "pong"
