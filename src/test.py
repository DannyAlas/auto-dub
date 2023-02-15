import requests
import re

def check_params(options: dict) -> dict:
    """
    checks that the required parameters are present and valid

    Parameters
    ----------
    options : dict
        dictionary of options
        SCHEMA:
        {
            "user_id": str,
            "order_id": str (id of the document in the orders collection for a user),
            "model_size": ["small", "medium", "large"],
            "video_language": ["auto", "en", "es", "fr", "de", "it", "pt", "ru"],
            "audio_url": str (url of the audio file)
        }
    
    15 chrs/second
    0.000016 per char MS VOICE

    0.000016 * 15 = 0.00024 per second
    


    Returns
    -------
    dict:
        response dictionary
        
    """
    # set the default response in case of unknown error
    response = {"status": "eroor", "message": "unknown error"}

    # check that the required parameters are present
    if not options.get("user_id"):
        response = {"status": "error", "message": "missing user_id"}
    elif not options.get("order_id"):
        response = {"status": "error", "message": "missing order_id"}
    elif not options.get("model_size") in ["small", "medium", "large", "large-v2"]:
        response = {"status": "error", "message": "invalid model"}
    elif not options.get("video_language") in ["auto", "en", "es", "fr", "de", "it", "pt", "ru"]:
        response = {"status": "error", "message": "invalid language"}
    elif not options.get("audio_url"):
        response = {"status": "error", "message": "invalid audio file"}
    
    # if all params present, check that they are is valid
    else:
        try:
            # check that the audio file is valid
            
            content_type = requests.get(options["audio_url"], timeout=10).headers.get(
                "content-type"
            )

            if content_type == "audio/mp3" or "audio/mpeg":
                pass
            else:
                response = {
                    "status": "error",
                    "message": f"Invalid audio file. Must be [audio/mp3] NOT [{content_type}]",
                }
                raise Exception(response.get("message"))

        except requests.exceptions.RequestException as e:
            print("EX REQUESTING")
            if re.search("404 Client Error: Not Found for url", str(e)):
                response = {"status": "error", "message": "Audio file not found"}
            elif re.search("Connection aborted", str(e)):
                response = {"status": "error", "message": "Connection aborted"}
            else:
                response = {"status": "error", "message": str(e)}
        except Exception as e:
            print("EXCEPTING")
            response = {"status": "error", "message": str(e)}

        finally:
            # id all params present and valid, return success response
            if response.get("status") == "error":
                return response
            response = {"status": "success", "message": f"All params present and valid"}

    return response
