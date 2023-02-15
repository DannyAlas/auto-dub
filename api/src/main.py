# main.py

from multiprocessing import AuthenticationError
import json
from fastapi import FastAPI, Request

from settings import Dubbing_Settings, Subtitle
from user import USER
from utils import download_srt_file, srt_to_dict, tanslated_srt_to_file
from translate import translate


app = FastAPI()


def authorize(request: Request):
    auth_headers = request.headers.get("authorization")
    assert auth_headers != None, "AUTHORIZATION ERROR: No Authorization Header"

    try:
        return USER(auth_headers.replace("Bearer ", ""))

    except Exception as e:
        raise AuthenticationError(str(e))


@app.post("/test/")
async def validate(request: Request, data: Subtitle):
    try:
        user = authorize(request)
    except AuthenticationError as e:
        return {"Authentication Error": str(e)}

    order = user.set_order_info(data.order_id)
    data.file = order.get("main_srt")

    # download srt -> to subs_dict -> run translate -> upload to db -> update order
    # download srt
    download_srt_file(order.get("main_srt"), "main.srt")

    # to subs_dict
    with open("main.srt", "r") as f:
        lines = f.readlines()
        subs_dict = srt_to_dict(lines, 0)

    # run translate
    t_subs_dict = translate(subs_dict=subs_dict, target_language=data.translation_target_language, formality=data.formality_preference)
    tanslated_srt_to_file(t_subs_dict, f"{data.order_id}-{data.translation_target_language}.srt")
    
    # upload to db and update order
    translated_srts = user.upload_translated_srt(f"{data.order_id}-{data.translation_target_language}.srt", data.order_id, data.translation_target_language)

    return {"message": "success", "order": translated_srts}
