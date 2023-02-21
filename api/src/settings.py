from concurrent.futures import process
from pathlib import Path
from typing import List, Literal, Union
from wsgiref.validate import validator

import pandas as pd
from pydantic import BaseModel, validator

ENCODINGS = [
    {
        "CODEC": "MP3",
        "NAME": "MPEG Audio Layer III",
        "LOSSLESS": "No",
        "NOTES": "MP3 encoding is a Beta feature and only available in v1p1beta1. See the RecognitionConfig reference documentation for details.",
    },
    {
        "CODEC": "FLAC",
        "NAME": "Free Lossless Audio Codec",
        "LOSSLESS": "Yes",
        "NOTES": "16-bit or 24-bit required for streams",
    },
    {
        "CODEC": "LINEAR16",
        "NAME": "Linear PCM",
        "LOSSLESS": "Yes",
        "NOTES": "16-bit linear pulse-code modulation (PCM) encoding. The header must contain the sample rate.",
    },
    {
        "CODEC": "MULAW",
        "NAME": "μ-law",
        "LOSSLESS": "Yes",
        "NOTES": "8-bit samples that compand 14-bit audio samples using G.711 PCMU/mu-law.",
    },
    {
        "CODEC": "AMR",
        "NAME": "Adaptive Multi-Rate Narrowband",
        "LOSSLESS": "No",
        "NOTES": "Adaptive Multi-Rate Narrowband",
    },
    {
        "CODEC": "AMR_WB",
        "NAME": "Adaptive Multi-Rate Wideband",
        "LOSSLESS": "No",
        "NOTES": "Adaptive Multi-Rate Wideband",
    },
    {
        "CODEC": "OGG_OPUS",
        "NAME": "Opus encoded audio frames in an Ogg container",
        "LOSSLESS": "No",
        "NOTES": "Opus encoded audio frames in an Ogg container",
    },
    {
        "CODEC": "SPEEX_WITH_HEADER_BYTE",
        "NAME": "Speex encoding supported in Ogg and WAV; Ogg container header must be byte-aligned.",
        "LOSSLESS": "No",
        "NOTES": "Speex encoding supported in Ogg and WAV; Ogg container header must be byte-aligned.",
    },
    {
        "CODEC": "WEBM_OPUS",
        "NAME": "Opus encoded audio frames in a WebM container",
        "LOSSLESS": "No",
        "NOTES": "Opus encoded audio frames in a WebM container",
    },
]
BCP_47_LANGUAGES: list = [
    "ar-SA",
    "cs-CZ",
    "da-DK",
    "de-DE",
    "el-GR",
    "en-AU",
    "en-GB",
    "en-IE",
    "en-US",
    "en-ZA",
    "es-ES",
    "es-MX",
    "fi-FI",
    "fr-CA",
    "fr-FR",
    "he-IL",
    "hi-IN",
    "hu-HU",
    "id-ID",
    "it-IT",
    "ja-JP",
    "ko-KR",
    "nl-BE",
    "nl-NL",
    "no-NO",
    "pl-PL",
    "pt-BR",
    "pt-PT",
    "ro-RO",
    "ru-RU",
    "sk-SK",
    "sv-SE",
    "th-TH",
    "tr-TR",
    "zh-CN",
    "zh-HK",
    "zh-TW",
]
GOOGLE_TANSLATION_LANGUAGES: dict = {
    "Afrikaans": "af",
    "Albanian": "sq",
    "Amharic": "am",
    "Arabic": "ar",
    "Armenian": "hy",
    "Assamese": "as",
    "Aymara": "ay",
    "Azerbaijani": "az",
    "Bambara": "bm",
    "Basque": "eu",
    "Belarusian": "be",
    "Bengali": "bn",
    "Bhojpuri": "	bho",
    "Bosnian": "bs",
    "Bulgarian": "bg",
    "Catalan": "ca",
    "Cebuano": "ceb",
    "Chinese (Simplified)": "zh-CN",
    "Chinese (Traditional)": "zh-TW",
    "Corsican": "co",
    "Croatian": "hr",
    "Czech": "cs",
    "Danish": "da",
    "Dhivehi": "dv",
    "Dogri": "doi",
    "Dutch": "nl",
    "English": "en",
    "Esperanto": "eo",
    "Estonian": "et",
    "Ewe": "ee",
    "Filipino (Tagalog)": "fil",
    "Finnish": "fi",
    "French": "fr",
    "Frisian": "fy",
    "Galician": "gl",
    "Georgian": "ka",
    "German": "de",
    "Greek": "el",
    "Guarani": "gn",
    "Gujarati": "gu",
    "Haitian Creole": "ht",
    "Hausa": "ha",
    "Hawaiian": "haw",
    "Hebrew": "he",
    "Hindi": "hi",
    "Hmong": "hmn",
    "Hungarian": "hu",
    "Icelandic": "is",
    "Igbo": "ig",
    "Ilocano": "ilo",
    "Indonesian": "id",
    "Irish": "ga",
    "Italian": "it",
    "Japanese": "ja",
    "Javanese": "jv",
    "Kannada": "kn",
    "Kazakh": "kk",
    "Khmer": "km",
    "Kinyarwanda": "rw",
    "Konkani": "gom",
    "Korean": "ko",
    "Krio": "kri",
    "Kurdish": "ku",
    "Kurdish (Sorani)": "ckb",
    "Kyrgyz": "ky",
    "Lao": "lo",
    "Latin": "la",
    "Latvian": "lv",
    "Lingala": "ln",
    "Lithuanian": "lt",
    "Luganda": "lg",
    "Luxembourgish": "lb",
    "Macedonian": "mk",
    "Maithili": "mai",
    "Malagasy": "mg",
    "Malay": "ms",
    "Malayalam": "ml",
    "Maltese": "mt",
    "Maori": "mi",
    "Marathi": "mr",
    "Meiteilon (Manipuri)": "mni-Mtei",
    "Mizo": "lus",
    "Mongolian": "mn",
    "Myanmar (Burmese)": "my",
    "Nepali": "ne",
    "Norwegian": "no",
    "Nyanja (Chichewa)": "ny",
    "Odia (Oriya)": "or",
    "Oromo": "om",
    "Pashto": "ps",
    "Persian": "fa",
    "Polish": "pl",
    "Portuguese (Portugal, Brazil)": "pt",
    "Punjabi": "pa",
    "Quechua": "qu",
    "Romanian": "ro",
    "Russian": "ru",
    "Samoan": "sm",
    "Sanskrit": "sa",
    "Scots Gaelic": "gd",
    "Sepedi": "nso",
    "Serbian": "sr",
    "Sesotho": "st",
    "Shona": "sn",
    "Sindhi": "sd",
    "Sinhala (Sinhalese)": "si",
    "Slovak": "sk",
    "Slovenian": "sl",
    "Somali": "so",
    "Spanish": "es",
    "Sundanese": "su",
    "Swahili": "sw",
    "Swedish": "sv",
    "Tagalog (Filipino)": "tl",
    "Tajik": "tg",
    "Tamil": "ta",
    "Tatar": "tt",
    "Telugu": "te",
    "Thai": "th",
    "Tigrinya": "ti",
    "Tsonga": "	ts",
    "Turkish": "tr",
    "Turkmen": "tk",
    "Twi (Akan)": "ak",
    "Ukrainian": "uk",
    "Urdu": "ur",
    "Uyghur": "ug",
    "Uzbek": "uz",
    "Vietnamese": "vi",
    "Welsh": "cy",
    "Xhosa": "xh",
    "Yiddish": "yi",
    "Yoruba": "yo",
    "Zulu": "zu",
}
DEEPL_TANSLATION_LANGUAGES: dict = {
    "Bulgarian": "BG",
    "Czech": "CS",
    "Danish": "DA",
    "German": "DE",
    "Greek": "EL",
    "English": "EN",
    "Spanish": "ES",
    "Estonian": "ET",
    "Finnish": "FI",
    "French": "FR",
    "Hungarian": "HU",
    "Indonesian": "ID",
    "Italian": "IT",
    "Japanese": "JA",
    "Korean": "KO",
    "Lithuanian": "LT",
    "Latvian": "LV",
    "Norwegian (Bokmål)": "NB",
    "Dutch": "NL",
    "Polish": "PL",
    "Portuguese (all Portuguese varieties mixed)": "PT",
    "Romanian": "RO",
    "Russian": "RU",
    "Slovak": "SK",
    "Slovenian": "SL",
    "Swedish": "SV",
    "Turkish": "TR",
    "Ukrainian": "UK",
    "Chinese": "ZH",
}
MICROSOFT_LANGUAGES: dict = {
    language["code"]: language
    for language in pd.read_csv(
        r"LANGUAGES/MS_LANGUAGES.csv",
        converters={
            "Text-to-speech voices": lambda x: x.strip("[]")
            .replace("'", "")
            .split(", ")
        },
    ).to_dict(orient="records")
}


class Main_Settings(BaseModel):
    """
    The main settings used by the dubbing program.

    Attributes:
    ----------
    skip_translation: bool = False
        weather or not to skip the translation step. If True, the program will not translate the subtitles

    skip_synthesize: bool = False
        weather or not to skip the synthesis step. If True, the program will not skip_synthesize

    stop_after_translation: bool = False
        weather or not to stop the program after the translation step. If True, the program will not continue after the translation step

    output_format: { "mp3", "aac", "wav" } = "mp3"
        the format/codec of the final audio file.

    synth_audio_encoding: str = "MP3"
        the audio encoding of the audio clips generated by the TTS service. Must be a codec from 'Supported Audio Encodings' section here: https://cloud.google.com/speech-to-text/docs/encoding#audio-encodings

    synth_sample_rate: { 24000, 48000 } = 24000
        the sample rate of the audio clips generated by the TTS service. This is usually 24KHz (24000), but some services like Azure offer higher quality audio at 48KHz (48000)

    two_pass_voice_synth: bool = True
        whether or not to use two passes to generate the audio clips. This will drastically improve the quality of the final result, BUT see note below

    force_stretch_with_twopass: bool = False
        weather or not to stretch the audio clips on the second pass. This will make the audio clips exactly the right length, but will degrade the quality of the audio. See note below

    azure_sentence_pause: Union[Literal["default"], int] = 80
        the pause in milliseconds that the TTS voice will pause after a period between sentences. Set it to "default" to keep it default which is quite slow. We found 80ms is pretty good. Note: Changing this from default adds about 60 characters per line to the total Azure character usage count.

    add_line_buffer_milliseconds: int = 30
        Adds a silence buffer between each spoken clip, but keeps the speech "centered" at the right spot so it's still synced. See notes.

    debug_mode: bool = False
        If true, will print out extra debug information and save the intermediate files to the output folder.

    Note
    ----
    `two_pass_voice_synth` if true will make it so instead of just stretching the audio clips, we will have the API generate new audio clips with adjusted speaking rates This can't be done on the first pass because we don't know how long the audio clips will be until we generate them.

    `force_stretch_with_twopass` if true will stretch the second-pass clip to be exactly equal to the desired length. However, this will degrade the voice and make it sound similar to if it was just 1-Pass

    `add_line_buffer_milliseconds` if true will add a silence buffer between each spoken clip, but keep the speech "centered" at the right spot so it's still synced. This is useful if your subtitles file has all the beginning and end timings right up against each other (no  buffer). The total extra between clips will be 2x this (end of first + start of second). Warning: setting this too high could result in the TTS speaking extremely fast to fit into remaining clip duration. Around 25 - 50 milliseconds is a good starting point.
    """

    skip_translation: bool = False
    skip_synthesize: bool = False
    stop_after_translation = False
    output_format = "mp3"
    synth_audio_encoding: str = "MP3"
    synth_sample_rate: int = 24000
    two_pass_voice_synth: bool = True
    force_stretch_with_twopass: bool = False
    azure_sentence_pause: Union[Literal["default"], int] = 80
    add_line_buffer_milliseconds: int = 0
    debug_mode: bool = False

    @validator("output_format")
    def output_format_must_be_valid(cls, v):
        if v not in ["mp3", "aac", "wav"]:
            raise ValueError("output_format must be one of: mp3, aac, wav")
        return v

    @validator("synth_audio_encoding")
    def synth_audio_encoding_must_be_valid(cls, v):
        if v not in [x["CODEC"] for x in ENCODINGS]:
            raise ValueError(
                "synth_audio_encoding must be one of: MP3, LINEAR16, OGG_OPUS"
            )
        return v

    @validator("synth_sample_rate")
    def synth_sample_rate_must_be_valid(cls, v):
        if v not in [24000, 48000]:
            raise ValueError("synth_sample_rate must be one of: 24000, 48000")
        return v

    @validator("azure_sentence_pause")
    def azure_sentence_pause_must_be_valid(cls, v):
        if type(v) != int:
            if v != "default":
                raise ValueError(
                    f"azure_sentence_pause must be one of: default, int. Not {type(v), v}"
                )
        return v


class Dubbing_Settings(BaseModel):
    """
    A single subtitle instance to process

    Attributes
    ----------

    original_language: str
        The BCP-47 language code for the original text language

    formality_preference: { "default", "more", "less" } = "default"
        applies to DeepL translations only - Whether to have it use more or less formal language.

    translation_target_language: str
        The language code to translate the subtitle to. Supported codes = translation_target_language_codes

    synth_language_code: str
        The BCP-47 language code to use for the TTS voice. Suported codes = microsoft_languages_codes

    synth_voice_name: str
        The name of the TTS voice to use. Supported voices = MICROSOFT_LANGUAGES_VOICES

    synth_voice_gender: str
        The gender of the voice. Note supported genders depend of the voice, see supported voices

    translation_formality: str
        The formality of the translation. Supported formality = ["default", "more", "less"]

    combine_subtitles: bool = True
        Whether or not to combine adjacent subtitles into a single line. This is useful for services like Azure which have a character limit per line. If the combination of two adjacent subtitle lines is below the `combine_subtitles_max_chars` and one starts at the same time the other ends, then they will be combined into a single line. This should improve the speech synthesis by reducing unnatural splits in spoken sentences.

    combine_subtitles_max_chars: int = 200
        The maximum number of characters that can be combined into a single line. This is useful for services like Azure which have a character limit per line. If the combination of two adjacent subtitle lines is below this amount and one starts at the same time the other ends, then they will be combined into a single line. This should improve the speech synthesis by reducing unnatural splits in spoken sentences.

    """

    combine_subtitles: bool = True
    combine_subtitles_max_chars: int = 200

    original_language: str = "en-US"
    formality_preference: str = "default"
    translation_target_language: str = "KO"
    synth_language_code: str = "es-MX"
    synth_voice_name: str = "es-MX-CecilioNeural"
    synth_voice_gender: str = "MALE"

    subs_dict: dict = {}

    @property
    def translation_target_language_codes(self) -> list:
        return list(DEEPL_TANSLATION_LANGUAGES.values())

    @property
    def microsoft_languages_codes(self) -> list:
        return [x for x in MICROSOFT_LANGUAGES]

    @property
    def microsoft_languages_voices(self) -> list:
        return [MICROSOFT_LANGUAGES[x]["voices"] for x in MICROSOFT_LANGUAGES]

    @validator("original_language")
    def original_language_must_be_valid(cls, v):
        if v not in BCP_47_LANGUAGES:
            raise ValueError("original_language must be a valid BCP-47 language code")
        return v

    @validator("formality_preference")
    def formality_preference_must_be_valid(cls, v):
        if v not in ["default", "more", "less"]:
            raise ValueError("formality_preference must be one of: default, more, less")
        return v

    @validator("translation_target_language")
    def translation_target_language_must_be_valid(cls, v):
        if v not in list(DEEPL_TANSLATION_LANGUAGES.values()):
            raise ValueError(
                "translation_target_language must be a valid DeepL language code. See translation_target_language_codes for a list of supported codes"
            )
        return v

    @validator("synth_language_code")
    def synth_language_code_must_be_valid(cls, v):
        if v not in [x for x in MICROSOFT_LANGUAGES]:
            raise ValueError(
                "synth_language_code must be a valid BCP-47 language code. See microsoft_languages_codes for a list of supported codes"
            )
        return v

    @validator("synth_voice_name", "synth_voice_gender")
    def synth_language_code_and_synth_voice_gender_must_match(cls, v, values):
        # TODO: figure this out later
        return v


class Order(BaseModel):
    """
    A single subtitle instance to process

    Attributes
    ----------

    order_id: str
        The order id of the request
    settings: Dubbing_Settings
        The dubbing settings to use
    dubbing_instances: List[Subtitle]
        A list of Subtitle objects to process

    """

    order_id: str = ""
    settings: Main_Settings = Main_Settings()
    dubbing_instances: List[Dubbing_Settings]

    @validator("settings")
    def settings_must_be_valid(cls, v):
        if not isinstance(v, Main_Settings):
            raise ValueError("dubbing_settings must be a valid Dubbing_Settings object")
        return v

    @validator("dubbing_instances")
    def instances_must_be_valid(cls, v):
        if not isinstance(v, list):
            raise ValueError("instances must be a list of `Dubbing_Settings`")
        for instance in v:
            if not isinstance(instance, Dubbing_Settings):
                raise ValueError("instances must of type `Dubbing_Settings`")
        return v


class Srt_Timestamp:
    """A class to represent a single SRT timestamp line.

    Attributes:
        srt_timestamps_line (str): The line of text from the SRT file that contains the start and end timestamps.
        start (str): The start timestamp in milliseconds.
        end (str): The end timestamp in milliseconds.
        duration (int): The duration of the timestamp in milliseconds.

    Methods:
        get_start(): Returns the start timestamp in milliseconds.
        get_end(): Returns the end timestamp in milliseconds.
        get_duration(): Returns the duration of the timestamp in milliseconds.
    """

    def __init__(self, srt_timestamps_line):
        self.srt_timestamps_line = srt_timestamps_line
        self.srt_timestamps_line_valid()

        self.start = self.get_start()
        self.end = self.get_end()
        self.duration = self.get_duration()

    def srt_timestamps_line_valid(self) -> bool:
        """Validates the SRT timestamp line."""
        from re import match

        if (
            match(
                r"(\d+:\d+:\d+,\d+)[^\S\n]+-->[^\S\n]+(\d+:\d+:\d+,\d+)",
                self.srt_timestamps_line,
            )
            is not None
        ):
            return True
        else:
            raise ValueError(f"Invalid SRT timestamp line: {self.srt_timestamps_line}")

    def get_start(self) -> str:
        start_ms = self.srt_timestamps_line.split(" --> ")[0]
        return start_ms

    def get_end(self) -> str:
        end_ms = self.srt_timestamps_line.split(" --> ")[1]
        return end_ms

    def get_duration(self) -> int:
        # convert start and end to int in milliseconds
        start_ms = (
            int(self.start.split(":")[0]) * 3600000
            + int(self.start.split(":")[1]) * 60000
            + int(self.start.split(":")[2].split(",")[0]) * 1000
            + int(self.start.split(":")[2].split(",")[1])
        )
        end_ms = (
            int(self.end.split(":")[0]) * 3600000
            + int(self.end.split(":")[1]) * 60000
            + int(self.end.split(":")[2].split(",")[0]) * 1000
            + int(self.end.split(":")[2].split(",")[1])
        )

        duration_ms = end_ms - start_ms
        return duration_ms

    def __repr__(self) -> str:
        return f"{self.start} --> {self.end}"

    def __eq__(self, other) -> bool:
        if isinstance(other, Srt_Timestamp):
            return (
                self.start == other.start
                and self.end == other.end
                and self.duration == other.duration
            )
        return False

    def __ne__(self, other) -> bool:
        if isinstance(other, Srt_Timestamp):
            return (
                self.start != other.start
                or self.end != other.end
                or self.duration != other.duration
            )
        return True
