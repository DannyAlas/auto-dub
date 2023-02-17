import os

from deepl_api import DEEPL_API
from translate_utils import (add_notranslate_tags_for_manual_translations,
                              add_notranslate_tags_from_notranslate_file,
                              combine_single_pass, process_response_text)
from utils import csv_to_dict, txt_to_list
import logging
from sys import stdout

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
    datefmt="%d/%b/%Y %H:%M:%S",
    stream=stdout)

def combine_subtitles_advanced(inputDict, maxCharacters=200):
    """Combines subtitle lines that are close together and have a similar speaking rate. Useful when sentences are split into multiple subtitle lines. Voice synthesis will have fewer unnatural pauses.

    TODO: REWRITE THIS FUNCTION AT SOME POINT, split into multiple functions with more options
    """
    charRateGoal = 20  # 20
    gapThreshold = 100  # The maximum gap between subtitles to combine
    noMorePossibleCombines = False
    # Convert dictionary to list of dictionaries of the values
    entryList = []
    
    logging.debug(f"CONVERTING DICT TO LIST - charRateGoal: {charRateGoal}, gapThreshold: {gapThreshold}, maxCharacters: {maxCharacters}")

    for key, value in inputDict.items():
        value["originalIndex"] = int(key) - 1
        entryList.append(value)

    while not noMorePossibleCombines:
        entryList, noMorePossibleCombines = combine_single_pass(
            entryList, charRateGoal, gapThreshold, maxCharacters
        )

    # Convert the list back to a dictionary then return it
    return dict(enumerate(entryList, start=1))


def translate(
    subs_dict: dict,
    target_language: str,
    formality: str = "default",
    combine_subtitles: bool = True,
    combine_max_characters: int = 200,
):
    """Translates a subtitle dictionary into the target language.

    Parameters
    ----------
    subs_dict: dict
        A dictionary containing subtitle information.
    target_language: str
        The target language to translate to.
    formality: str default="default"
        The formality of the translation. Can be "default", "more" or "less".
    combine_subtitles: bool default=True
        Whether to combine subtitles that are close together and have a similar speaking rate. Useful when sentences are split into multiple subtitle lines. Voice synthesis will have fewer unnatural pauses.
    combine_max_characters: int default=200
        The maximum number of characters to combine subtitles into if combine_subtitles is true.
    
    Returns
    -------
    dict
        A dictionary containing the translated subtitle information.

    """
    logging.debug(f"TRANSLATING - target_language: {target_language}, formality: {formality}, combine_subtitles: {combine_subtitles}, combine_max_characters: {combine_max_characters}")

    noTranslateOverrideFile = os.path.abspath(
        "SSML_Customization/dont_translate_phrases.txt"
    )
    manualTranslationOverrideFile = os.path.abspath(
        "SSML_Customization/Manual_Translations.csv"
    )
    urlListFile = os.path.abspath("SSML_Customization/url_list.txt")

    # put them into dictionaries
    dontTranslateList = txt_to_list(noTranslateOverrideFile)
    manualTranslationsDict = csv_to_dict(manualTranslationOverrideFile)
    urlList = txt_to_list(urlListFile)
    textToTranslate = []

    deepl_api = DEEPL_API()

    for key in subs_dict:
        originalText = subs_dict[key]["text"]
        # Add any 'notranslate' tags to the text
        processedText = add_notranslate_tags_from_notranslate_file(
            originalText, dontTranslateList
        )
        processedText = add_notranslate_tags_from_notranslate_file(
            processedText, urlList
        )
        processedText = add_notranslate_tags_for_manual_translations(
            processedText, target_language
        )

        # Add the text to the list of text to be translated
        textToTranslate.append(processedText)

    logging.debug("TAGS SET")

    codepoints = 0
    for text in textToTranslate:
        codepoints += len(text.encode("utf-8"))

    if codepoints > 120000:
        chunkSize = 400
        chunkedTexts = [
            textToTranslate[x : x + chunkSize]
            for x in range(0, len(textToTranslate), chunkSize)
        ]

        # Send and receive the batch requests
        for j, chunk in enumerate(chunkedTexts):

            logging.debug(f"[DeepL] Translating text group {j+1} of {len(chunkedTexts)}")

            # Send the request
            result = deepl_api.translate_text(
                chunk,
                target_lang=target_language,
                formality=formality,
                tag_handling="html",
            )

            # Extract the translated texts from the response
            translatedTexts = [process_response_text(result[i].text, target_language) for i in range(len(result))]  # type: ignore

            # Add the translated texts to the dictionary
            for i in range(chunkSize):
                key = str((i + 1 + j * chunkSize))
                subs_dict[key]["translated_text"] = process_response_text(
                    translatedTexts[i], target_language
                )
                # Print progress, ovwerwrite the same line
                logging.debug(f" Translated with DeepL: {key} of {len(subs_dict)}")
    else:
        
        logging.debug("Sending request to DeepL")
        
        result = deepl_api.translate_text(
            text=textToTranslate,
            target_lang=target_language,
            formality=formality,
            tag_handling="html",
        )
        
        logging.debug("Received response from DeepL")
        
        # Add the translated texts to the dictionary
        for i, key in enumerate(subs_dict):
            subs_dict[key]["translated_text"] = process_response_text(result[i].text, target_language)  # type: ignore

        logging.debug("Added translated texts to dictionary")

    # Combine subtitles if requested
    if combine_subtitles:
        subs_dict = combine_subtitles_advanced(subs_dict, combine_max_characters)

    logging.debug("Returning dictionary")

    return subs_dict
