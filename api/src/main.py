# main.py

from multiprocessing import AuthenticationError
import json
import os
from fastapi import FastAPI, Request

from settings import Dubbing_Settings, Order
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
async def test(request: Request, data: Order):

    try:
        user = authorize(request)
    except AuthenticationError as e:
        return {"Authentication Error": str(e)}

    order = user.initialize_db_order(order=data)

    
    # download srt -> to subs_dict -> run translate -> upload to db -> update order
    # download srt
    try:
        # ensure temp_dir exists
        if not os.path.exists("temp/srt"):
            os.mkdir("temp/srt")

        
        # download main srt
        main_srt_url = user.create_download_url(path=order.get("main_srt"))
        file = download_srt_file(main_srt_url, "temp/main.srt")
    except Exception as e:
        return {"Error downloading file": str(e)}

    # to subs_dict
    try:
        with open(file, "r") as f:
            lines = f.readlines()
            subs_dict = srt_to_dict(lines, order.get("dubbing_settings").get("add_line_buffer_milliseconds"))
    except Exception as e:
        return {"Error converting srt to dict": str(e)}


    # run translate
    uploads = {}
    for i in order.get("dubbing_instances"):
        try:
            t_subs_dict = translate(
                subs_dict=subs_dict, 
                target_language=i.get("translation_target_language"), 
                formality=i.get("formality_preference"),
                combine_subtitles=i.get("combine_subtitles"),
                combine_max_characters=i.get("combine_subtitles_max_chars"),
                )
            
            with open(f"temp/{i.get('translation_target_language')}.json", "w") as f:
                out = {"order_settings": data.settings.dict(), "dubbing_instance": i, "subs_dict": subs_dict, "t_subs_dict": t_subs_dict}
                f.write(json.dumps(out, indent=4))
            
            tanslated_srt_to_file(t_subs_dict, f"temp/srt/{i.get('translation_target_language')}.srt")
            
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
                
                x_subsDict = synthesize_text_azure_batch(subsDict = t_subs_dict, langDict = langDict, skipSynthesize=False, secondPass=False, azureSentencePause=80)

                print(x_subsDict)

    return {'subsDict': "x_subsDict"}