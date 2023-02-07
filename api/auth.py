#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# Google Authentication Modules
from googleapiclient.discovery import build
import os
import deepl
from dotenv import load_dotenv

# load enviorment variables
load_dotenv()


def google_auth(api_key: str):

    # GOOGLE_TTS_API = build('texttospeech', 'v1', developerKey=api_key)
    GOOGLE_TRANSLATE_API = build("translate", "v3beta1", developerKey=api_key)

    return GOOGLE_TRANSLATE_API


class DEEPL_AUTH:
    """DEEPL API Authentication Class"""

    def __init__(self):
        self.deeplApiKey = os.environ.get("DEEPL_API_KEY")
        if self.deeplApiKey:
            self.deepl_auth_object = deepl.Translator(self.deeplApiKey)
        else:
            raise Exception("DEEPL_API_KEY not found in .env file")
