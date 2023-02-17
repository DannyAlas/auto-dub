# main.py

from multiprocessing import AuthenticationError
import json
import os
from fastapi import FastAPI, Request

from settings import Dubbing_Settings, Order
from user import USER
from utils import download_srt_file, srt_to_dict, tanslated_srt_to_file
from translate import translate
from pathlib import Path
from typing import Any
import logging
from sys import stdout
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=[10 if os.environ.get("DEBUG") == "True" else 20][0],
    format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
    datefmt="%d/%b/%Y %H:%M:%S",
    stream=stdout)

app = FastAPI()

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

def download_main_srt_file(user: USER, order: dict) -> Path:
    """
    Downloads main srt file from storage and saves it to temp/main.srt
    
    Parameters
    ----------
    user (USER):
        User object
    order (dict):
        Order info
    
    Returns
    -------
    Path:
        Path to main.srt
    
    Raises
    ------
    Exception:
        Error downloading srt file
    """
    # ensure temp_dir exists
    logging.debug("CREATING TEMP DIR")
    if not os.path.exists("temp/srt"):
        os.mkdir("temp/srt")
    
    # download main srt
    logging.debug(f"CREATING DOWNLOAD URL. PATH: {order.get('main_srt')}")
    main_srt_url = user.create_download_url(path=order.get("main_srt"))

    return download_srt_file(main_srt_url, "temp/main.srt")

def to_subs_dict(file: Path, order: dict) -> dict:
    try:
        dubbing_settings = order["dubbing_settings"]
        logging.debug(f"DUBBING SETTINGS: {dubbing_settings}")
        assert dubbing_settings.get("add_line_buffer_milliseconds") != None, "No add_line_buffer_milliseconds"

        with open(file, "r") as f:
            lines = f.readlines()
            logging.debug(f"SUBS LINES READ. LEN: {len(lines)}")
            subs_dict = srt_to_dict(lines, dubbing_settings.get("add_line_buffer_milliseconds"))
            return subs_dict
    except Exception as e:
        raise e

def del_temp_files():
    logging.debug("DELETING TEMP FILES")
    if os.path.exists("temp"):
        os.system("rm -rf temp")

@app.post("/translate/")
async def test(request: Request, data: Order) -> Any:
    """Translate endpoint. Translates srt file and uploads to storage

    Flow:
        1. Authorize user
        2. Initialize order in db and storage
        3. Download srt from storage
        4. Convert srt to subs dict
        5. Translate
        6. Upload translation to storage
        7. Update order in db


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
        logging.debug("DOWNLOADING SRT")
        file = download_main_srt_file(user, order)
    except Exception as e:
        return {"Error downloading srt": str(e)}

    # to subs_dict
    try:
        logging.debug("CONVERTING SRT TO DICT")
        subs_dict = to_subs_dict(file, order)
    except Exception as e:
        return {"Error converting srt to dict": str(e)}


    # run translate
    uploads = {}
    for i in order.get("dubbing_instances"):
        try:
            logging.debug(f"TRANSLATING: {i.get('translation_target_language')}")
            t_subs_dict = translate(
                subs_dict=subs_dict, 
                target_language=i.get("translation_target_language"), 
                formality=i.get("formality_preference"),
                combine_subtitles=i.get("combine_subtitles"),
                combine_max_characters=i.get("combine_subtitles_max_chars"),
                )
            
            logging.debug(f"TRANSLATED: {i.get('translation_target_language')}")
            with open(f"temp/{i.get('translation_target_language')}.json", "w") as f:
                logging.debug(f"WRITING TRANSLATED JSON: {i.get('translation_target_language')}")
                out = {"order_settings": data.settings.dict(), "dubbing_instance": i, "subs_dict": subs_dict, "t_subs_dict": t_subs_dict}
                f.write(json.dumps(out, indent=4))
                logging.debug(f"WRITTEN TRANSLATED JSON TO: {Path(f.name).absolute()}")
            
            logging.debug(f"CONVERTING TRANSLATED SRT TO FILE: {i.get('translation_target_language')}")
            tanslated_srt_to_file(t_subs_dict, f"temp/srt/{i.get('translation_target_language')}.srt")
            
            logging.debug(f"UPLOADING TRANSLATED SRT TO DB: {i.get('translation_target_language')}")
            uploads = user.upload_translated_srt(file=f"temp/srt/{i.get('translation_target_language')}.srt", order_id=order.get("order_id"), language=i.get("translation_target_language"))

        except Exception as e:
            return {"Error translating": str(e)}
        

    return {"message": "success", "order": uploads }


@app.get("/language_codes/")
async def get_language_codes():
    d = Dubbing_Settings()
    return {"message": "language codes", "data": d.microsoft_languages_codes}

@app.post("/dub/")
async def dub(request: Request, data: Dubbing_Settings):
    
    from voice_synth import synthesize_text_azure_batch

    for trans_file in os.listdir("temp"):
        if trans_file.endswith(".json"):
            with open(os.path.abspath(f"temp/{trans_file}"), "r") as f:
                t_sub = json.loads(f.read())
                order_settings = t_sub.get("order_settings")
                t_subs_dict = t_sub.get("t_subs_dict")
                langDict = t_sub.get("dubbing_instance")
                
                x_subsDict = synthesize_text_azure_batch(subsDict = t_subs_dict, langDict = langDict, skipSynthesize=order_settings.get("skip_synthesize"), secondPass=False, azureSentencePause=80)

                print(x_subsDict)

    return {'subsDict': "x_subsDict"}