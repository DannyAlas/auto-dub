import os
import utils
import re
import html
from typing import List, Dict, Any, Union

# Import files from SSML_Customization folder
noTranslateOverrideFile = os.path.join('SSML_Customization', 'dont_translate_phrases.txt')
manualTranslationOverrideFile = os.path.join('SSML_Customization', 'Manual_Translations.csv')
urlListFile = os.path.join('SSML_Customization', 'url_list.txt')
# put them into dictionaries
dontTranslateList = utils.txt_to_list(noTranslateOverrideFile)
manualTranslationsDict = utils.csv_to_dict(manualTranslationOverrideFile)
urlList = utils.txt_to_list(urlListFile)

#================================================================================================
#                           Helper Functions for translating text
#================================================================================================

def add_notranslate_tags_from_notranslate_file(text, phraseList) -> Any | str:
    """
    This function adds <span class="notranslate"> around words in the phraseList
    
    Parameters
    ----------

    phraseLis: str
        A list of words to not translate. For example, if the phraseList is ['example', 'list'], and the text is 'This is an example list', the text will be translated as 'This is an <span class="notranslate">example</span> <span class="notranslate">list</span>'
    
    Returns
    -------
    str
        The text with <span class="notranslate"> around words in the phraseList

    """
    for word in phraseList:
        findWordRegex = rf'(\b["\'()]?{word}[.,!?()]?["\']?\b)' # Find the word, with optional punctuation after, and optional quotes before or after
        text = re.sub(findWordRegex, r'<span class="notranslate">\1</span>', text, flags=re.IGNORECASE)
    return text

def remove_notranslate_tags(text) -> Any | str:
    """
    This function removes <span class="notranslate"> tags from text

    Parameters
    ----------
    text: str
        The text to remove <span class="notranslate"> tags from
    
    Returns
    -------
    str
        The text with <span class="notranslate"> tags removed

    """

    text = text.replace('<span class="notranslate">', '').replace('</span>', '')
    return text

def add_notranslate_tags_for_manual_translations(text, langcode) -> Any | str:
    """
    This function adds <span class="notranslate"> around words in the manualTranslationsDict
    
    Parameters
    ----------
    text: str
        The text to add <span class="notranslate"> tags to
    langcode: str
        The language code of the text. For example, if the text is in English, the langcode is 'en'
    
    Returns
    -------
    str
        The text with <span class="notranslate"> around words in the manualTranslationsDict

    """
    for manualTranslatedText in manualTranslationsDict:
        # Only replace text if the language matches the entry in the manual translations file
        if manualTranslatedText['Language Code'] == langcode: 
            originalText = manualTranslatedText['Original Text']
            findWordRegex = rf'(\b["\'()]?{originalText}[.,!?()]?["\']?\b)'
            text = re.sub(findWordRegex, r'<span class="notranslate">\1</span>', text, flags=re.IGNORECASE)
    return text

def replace_manual_translations(text, langcode) -> Any:
    """
    This function replaces words in the manualTranslationsDict with their translations

    Parameters
    ----------
    text: str
        The text to replace words in
    langcode: str
        The language code of the text. For example, if the text is in English, the langcode is 'en'
    
    Returns
    -------
    str
        The text with words in the manualTranslationsDict replaced with their translations
    
    """
    for manualTranslatedText in manualTranslationsDict:
        # Only replace text if the language matches the entry in the manual translations file
        if manualTranslatedText['Language Code'] == langcode: 
            originalText = manualTranslatedText['Original Text']
            translatedText = manualTranslatedText['Translated Text']
            findWordRegex = rf'(\b["\'()]?{originalText}[.,!?()]?["\']?\b)'
            text = re.sub(findWordRegex, translatedText, text, flags=re.IGNORECASE)
    return text

#================================================================================================
#                           Functions for translating text
#================================================================================================

def process_response_text(text, targetLanguage) -> Any:
    """
    This function processes the text returned from the API response

    Parameters
    ----------
    text: str
        The text to process
    targetLanguage: str
        The language code of the text. For example, if the text is in English, the langcode is 'en'

    Returns
    -------
    str
        The processed text
    
    """
    text = html.unescape(text)
    text = remove_notranslate_tags(text)
    text = replace_manual_translations(text, targetLanguage)
    return text

# Translate the text entries of the dictionary
def translate_dictionary(inputSubsDict, langDict, skipTranslation=False):
    targetLanguage = langDict['targetLanguage']
    translateService = langDict['translateService']
    formality = langDict['formality']

    # Create a container for all the text to be translated
    textToTranslate = []

    for key in inputSubsDict:
        originalText = inputSubsDict[key]['text']
        # Add any 'notranslate' tags to the text
        processedText = add_notranslate_tags_from_notranslate_file(originalText, dontTranslateList)
        processedText = add_notranslate_tags_from_notranslate_file(processedText, urlList)
        processedText = add_notranslate_tags_for_manual_translations(processedText, targetLanguage)

        # Add the text to the list of text to be translated
        textToTranslate.append(processedText)
   
    # Calculate the total number of utf-8 codepoints
    codepoints = 0
    for text in textToTranslate:
        codepoints += len(text.encode("utf-8"))
    
    # If the codepoints are greater than 28000, split the request into multiple
    # Google's API limit is 30000 Utf-8 codepoints per request, while DeepL's is 130000, but we leave some room just in case
    if skipTranslation == False:
        if translateService == 'google' and codepoints > 27000 or translateService == 'deepl' and codepoints > 120000:
            # GPT-3 Description of what the following line does:
            # If Google Translate is being used:
            # Splits the list of text to be translated into smaller chunks of 100 texts.
            # It does this by looping over the list in steps of 100, and slicing out each chunk from the original list. 
            # Each chunk is appended to a new list, chunkedTexts, which then contains the text to be translated in chunks.
            # The same thing is done for DeepL, but the chunk size is 400 instead of 100.
            chunkSize = 100 if translateService == 'google' else 400
            chunkedTexts = [textToTranslate[x:x+chunkSize] for x in range(0, len(textToTranslate), chunkSize)]
            
            # Send and receive the batch requests
            for j,chunk in enumerate(chunkedTexts):
                
                # Send the request
                if translateService == 'google':
                    # Print status with progress
                    print(f'[Google] Translating text group {j+1} of {len(chunkedTexts)}')
                    response = auth.GOOGLE_TRANSLATE_API.projects().translateText(
                        parent='projects/' + googleProjectID,
                        body={
                            'contents': chunk,
                            'sourceLanguageCode': originalLanguage,
                            'targetLanguageCode': targetLanguage,
                            'mimeType': 'text/html',
                            #'model': 'nmt',
                            #'glossaryConfig': {}
                        }
                    ).execute()

                    # Extract the translated texts from the response
                    translatedTexts = [process_response_text(response['translations'][i]['translatedText'], targetLanguage) for i in range(len(response['translations']))]

                    # Add the translated texts to the dictionary
                    # Divide the dictionary into chunks of 100
                    for i in range(chunkSize):
                        key = str((i+1+j*chunkSize))
                        inputSubsDict[key]['translated_text'] = process_response_text(translatedTexts[i], targetLanguage)
                        # Print progress, ovwerwrite the same line
                        print(f' Translated with Google: {key} of {len(inputSubsDict)}', end='\r')

                elif translateService == 'deepl':
                    print(f'[DeepL] Translating text group {j+1} of {len(chunkedTexts)}')

                    # Send the request
                    result = auth.DEEPL_API.translate_text(chunk, target_lang=targetLanguage, formality=formality, tag_handling='html')
                    
                    # Extract the translated texts from the response
                    translatedTexts = [process_response_text(result[i].text, targetLanguage) for i in range(len(result))]

                    # Add the translated texts to the dictionary
                    for i in range(chunkSize):
                        key = str((i+1+j*chunkSize))
                        inputSubsDict[key]['translated_text'] = process_response_text(translatedTexts[i], targetLanguage)
                        # Print progress, ovwerwrite the same line
                        print(f' Translated with DeepL: {key} of {len(inputSubsDict)}', end='\r')
                else:
                    print("Error: Invalid translate_service setting. Only 'google' and 'deepl' are supported.")
                    sys.exit()
                
        else:
            if translateService == 'google':
                print("Translating text using Google...")
                response = auth.GOOGLE_TRANSLATE_API.projects().translateText(
                    parent='projects/' + googleProjectID,
                    body={
                        'contents':textToTranslate,
                        'sourceLanguageCode': originalLanguage,
                        'targetLanguageCode': targetLanguage,
                        'mimeType': 'text/html',
                        #'model': 'nmt',
                        #'glossaryConfig': {}
                    }
                ).execute()
                translatedTexts = [process_response_text(response['translations'][i]['translatedText'], targetLanguage) for i in range(len(response['translations']))]
                
                # Add the translated texts to the dictionary
                for i, key in enumerate(inputSubsDict):
                    inputSubsDict[key]['translated_text'] = process_response_text(translatedTexts[i], targetLanguage)
                    # Print progress, overwrite the same line
                    print(f' Translated: {key} of {len(inputSubsDict)}', end='\r')

            elif translateService == 'deepl':
                print("Translating text using DeepL...")

                # Send the request
                result = auth.DEEPL_API.translate_text(textToTranslate, target_lang=targetLanguage, formality=formality, tag_handling='html')

                # Add the translated texts to the dictionary
                for i, key in enumerate(inputSubsDict):
                    inputSubsDict[key]['translated_text'] = process_response_text(result[i].text, targetLanguage)
                    # Print progress, overwrite the same line
                    print(f' Translated: {key} of {len(inputSubsDict)}', end='\r')
            else:
                print("Error: Invalid translate_service setting. Only 'google' and 'deepl' are supported.")
                sys.exit()
    else:
        for key in inputSubsDict:
            inputSubsDict[key]['translated_text'] = process_response_text(inputSubsDict[key]['text'], targetLanguage) # Skips translating, such as for testing
    print("                                                  ")

    # # Debug export inputSubsDict as json for offline testing
    # import json
    # with open('inputSubsDict.json', 'w') as f:
    #     json.dump(inputSubsDict, f)

    # # DEBUG import inputSubsDict from json for offline testing
    # import json
    # with open('inputSubsDict.json', 'r') as f:
    #     inputSubsDict = json.load(f)

    combinedProcessedDict = combine_subtitles_advanced(inputSubsDict, combineMaxChars)

    if skipTranslation == False or debugMode == True:
        # Use video file name to use in the name of the translate srt file, also display regular language name
        lang = langcodes.get(targetLanguage).display_name()
        if debugMode:
            if os.path.isfile(originalVideoFile):
                translatedSrtFileName = pathlib.Path(originalVideoFile).stem + f" - {lang} - {targetLanguage}.DEBUG.txt"
            else:
                translatedSrtFileName = "debug" + f" - {lang} - {targetLanguage}.DEBUG.txt"
        else:
            translatedSrtFileName = pathlib.Path(originalVideoFile).stem + f" - {lang} - {targetLanguage}.srt"
        # Set path to save translated srt file
        translatedSrtFileName = os.path.join(outputFolder, translatedSrtFileName)
        # Write new srt file with translated text
        with open(translatedSrtFileName, 'w', encoding='utf-8-sig') as f:
            for key in combinedProcessedDict:
                f.write(str(key) + '\n')
                f.write(combinedProcessedDict[key]['srt_timestamps_line'] + '\n')
                f.write(combinedProcessedDict[key]['translated_text'] + '\n')
                if debugMode:
                    f.write(f"DEBUG: duration_ms = {combinedProcessedDict[key]['duration_ms']}" + '\n')
                    f.write(f"DEBUG: char_rate = {combinedProcessedDict[key]['char_rate']}" + '\n')
                    f.write(f"DEBUG: start_ms = {combinedProcessedDict[key]['start_ms']}" + '\n')
                    f.write(f"DEBUG: end_ms = {combinedProcessedDict[key]['end_ms']}" + '\n')
                    f.write(f"DEBUG: start_ms_buffered = {combinedProcessedDict[key]['start_ms_buffered']}" + '\n')
                    f.write(f"DEBUG: end_ms_buffered = {combinedProcessedDict[key]['end_ms_buffered']}" + '\n')
                f.write('\n')

    return combinedProcessedDict


