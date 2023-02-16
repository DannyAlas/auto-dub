import json
import os
import re
import datetime
import copy
from typing import Literal
import azure_batch
import time
import zipfile
import io
from utils import parseBool, csv_to_dict, txt_to_list
from urllib.request import urlopen

from typing import Union, Literal

interpretAsOverrideFile = os.path.abspath('SSML_Customization/interpret-as.csv')
interpretAsEntries = csv_to_dict(interpretAsOverrideFile)
urlListFile = os.path.abspath('SSML_Customization/url_list.txt')
urlList = txt_to_list(urlListFile)
aliasOverrideFile = os.path.abspath('SSML_Customization/aliases.csv')
aliasEntries = csv_to_dict(aliasOverrideFile)
phonemeFile = os.path.abspath('SSML_Customization/Phoneme_Pronunciation.csv')
phonemeEntries = csv_to_dict(phonemeFile)

def add_interpretas_tags(text):
    # Add interpret-as tags from interpret-as.csv
    for entryDict in interpretAsEntries:
        # Get entry info
        entryText = entryDict['Text']
        entryInterpretAsType = entryDict['interpret-as Type']
        isCaseSensitive = parseBool(entryDict['Case Sensitive (True/False)'])
        entryFormat = entryDict['Format (Optional)']

        # Create say-as tag
        if entryFormat == "":
            sayAsTagStart = rf'<say-as interpret-as="{entryInterpretAsType}">'
        else:
            sayAsTagStart = rf'<say-as interpret-as="{entryInterpretAsType}" format="{entryFormat}">'
        
        # Find and replace the word
        findWordRegex = rf'(\b["\']?{entryText}[.,!?]?["\']?\b)' # Find the word, with optional punctuation after, and optional quotes before or after
        if isCaseSensitive:
            text = re.sub(findWordRegex, rf'{sayAsTagStart}\1</say-as>', text) # Uses group reference, so remember regex must be in parentheses
            
        else:
            text = re.sub(findWordRegex, rf'{sayAsTagStart}\1</say-as>', text, flags=re.IGNORECASE)

    # Add interpret-as tags from url_list.txt
    for url in urlList:
        # This regex expression will match the top level domain extension, and the punctuation before/after it, and any periods, slashes or colons
        # It will then put the say-as characters tag around all matches
        punctuationRegex = re.compile(r'((?:\.[a-z]{2,6}(?:\/|$|\s))|(?:[\.\/:]+))') 
        taggedURL = re.sub(punctuationRegex, r'<say-as interpret-as="characters">\1</say-as>', url)
        # Replace any instances of the URL with the tagged version
        text = text.replace(url, taggedURL)

    return text

def add_alias_tags(text):
    for entryDict in aliasEntries:
        # Get entry info
        entryText = entryDict['Original Text']
        entryAlias = entryDict['Alias']
        if entryDict['Case Sensitive (True/False)'] == "":
            isCaseSensitive = False
        else:
            isCaseSensitive = parseBool(entryDict['Case Sensitive (True/False)'])

        # Find and replace the word
        findWordRegex = rf'\b["\'()]?{entryText}[.,!?()]?["\']?\b' # Find the word, with optional punctuation after, and optional quotes before or after
        if isCaseSensitive:
            text = re.sub(findWordRegex, rf'{entryAlias}', text)
        else:
            text = re.sub(findWordRegex, rf'{entryAlias}', text, flags=re.IGNORECASE)
    return text


# Uses the phoneme pronunciation file to add phoneme tags to the text
def add_phoneme_tags(text):
    for entryDict in phonemeEntries:
        # Get entry info
        entryText = entryDict['Text']
        entryPhoneme = entryDict['Phonetic Pronunciation']
        entryAlphabet = entryDict['Phonetic Alphabet']

        if entryDict['Case Sensitive (True/False)'] == "":
            isCaseSensitive = False
        else:
            isCaseSensitive = parseBool(entryDict['Case Sensitive (True/False)'])

        # Find and replace the word
        findWordRegex = rf'(\b["\'()]?{entryText}[.,!?()]?["\']?\b)' # Find the word, with optional punctuation after, and optional quotes before or after
        if isCaseSensitive:
            text = re.sub(findWordRegex, rf'<phoneme alphabet="ipa" ph="{entryPhoneme}">\1</phoneme>', text)
        else:
            text = re.sub(findWordRegex, rf'<phoneme alphabet="{entryAlphabet}" ph="{entryPhoneme}">\1</phoneme>', text, flags=re.IGNORECASE)
    return text

def add_all_pronunciation_overrides(text):
    text = add_interpretas_tags(text)
    text = add_alias_tags(text)
    text = add_phoneme_tags(text)
    return text

def format_percentage_change(speedFactor):
    # Determine speedFactor value for Azure TTS. It should be either 'default' or a relative change.
    if speedFactor == 1.0:
        rate = 'default'
    else:
        # Whether to add a plus sign to the number to relative change. A negative will automatically be added
        if speedFactor >= 1.0:
            percentSign = '+'
        else:
            percentSign = ''
        # Convert speedFactor float value to a relative percentage    
        rate = percentSign + str(round((speedFactor - 1.0) * 100, 5)) + '%'
    return rate

def synthesize_text_azure_batch(subsDict, langDict, skipSynthesize=False, secondPass=False, azureSentencePause: Union[Literal["default"], int] = "default"):
    # Write speed factor to subsDict in correct format
    for key, value in subsDict.items():
        if secondPass:
            subsDict[key]['speed_factor'] = format_percentage_change(subsDict[key]['speed_factor'])
        else:
            #subsDict[key]['speed_factor'] = float(1.0)
            subsDict[key]['speed_factor'] = 'default'

    def create_request_payload(remainingEntriesDict):
        # Create SSML for all subtitles
        ssmlJson = []
        payloadSizeInBytes = 0
        tempDict = dict(remainingEntriesDict) # Need to do this to avoid changing the original dict which would mess with the loop

        for key, value in tempDict.items():
            rate = tempDict[key]['speed_factor']
            text = tempDict[key]['translated_text']
            language = langDict['synth_language_code']
            voice = langDict['synth_voice_name']

            # Create strings for prosody tags. Only add them if rate is not default, because azure charges for characters of optional tags
            if rate == 'default':
                pOpenTag = ''
                pCloseTag = ''
            else:
                pOpenTag = f"<prosody rate='{rate}'>"
                pCloseTag = '</prosody>'

            # Create string for sentence pauses, if not default
            if not azureSentencePause == 'default' and type(azureSentencePause) == int:
                pauseTag = f'<mstts:silence type="Sentenceboundary-exact" value="{azureSentencePause}ms"/>'
            else:
                pauseTag = ''

            # Process text using pronunciation customization set by user
            text = add_all_pronunciation_overrides(text)

            # Create the SSML for each subtitle
            ssml = f"<speak version='1.0' xml:lang='{language}' xmlns='http://www.w3.org/2001/10/synthesis' " \
            "xmlns:mstts='http://www.w3.org/2001/mstts'>" \
            f"<voice name='{voice}'>{pauseTag}" \
            f"{pOpenTag}{text}{pCloseTag}</voice></speak>"
            ssmlJson.append({"text": ssml})

            # Construct request payload with SSML
            # Reconstruct payload with every loop with new SSML so that the payload size is accurate
            now = datetime.datetime.now()
            pendingPayload = {
                'displayName': langDict['synth_language_code'] + '-' + now.strftime("%Y-%m-%d %H:%M:%S"),
                'description': 'Batch synthesis of ' + langDict['synth_language_code'] + ' subtitles',
                "textType": "SSML",
                # To use custom voice, see original example code script linked from azure_batch.py
                "inputs": ssmlJson,
                "properties": {
                    "outputFormat": "audio-48khz-192kbitrate-mono-mp3",
                    "wordBoundaryEnabled": False,
                    "sentenceBoundaryEnabled": False,
                    "concatenateResult": False,
                    "decompressOutputFiles": False
                },
            }
            # Azure TTS Batch requests require payload must be under 500 kilobytes, so check payload is under 500,000 bytes. Not sure if they actually mean kibibytes, assume worst case.
            # Payload will be formatted as json so must account for that too by doing json.dumps(), otherwise calculated size will be inaccurate
            payloadSizeInBytes = len(str(json.dumps(pendingPayload)).encode('utf-8')) 

            if payloadSizeInBytes > 495000 or len(ssmlJson) > 995: # Leave some room for anything unexpected. Also number of inputs must be below 1000
                # If payload would be too large, ignore the last entry and break out of loop
                return payload, remainingEntriesDict # type: ignore
            else:
                payload = copy.deepcopy(pendingPayload) # Must make deepycopy otherwise ssmlJson will be updated in both instead of just pendingPayload
                # Remove entry from remainingEntriesDict if it was added to payload
                remainingEntriesDict.pop(key)                


        # If all the rest of the entries fit, return the payload
        return payload, remainingEntriesDict # type: ignore
    # ------------------------- End create_request_payload() -----------------------------------


    # Create payloads, split into multiple if necessary
    payloadList = []
    remainingPayloadEntriesDict = dict(subsDict) # Will remove entries as they are added to payloads
    while len(remainingPayloadEntriesDict) > 0:
        payloadToAppend, remainingPayloadEntriesDict = create_request_payload(remainingPayloadEntriesDict)
        payloadList.append(payloadToAppend)
    
    # Tell user if request will be broken up into multiple payloads
    if len(payloadList) > 1:
        print(f'Payload will be broken up into {len(payloadList)} requests (due to Azure size limitations).')

    # Use to keep track of filenames downloaded via separate zip files. WIll remove as they are downloaded
    remainingDownloadedEntriesList = list(subsDict.keys())

    # Clear out workingFolder
    # for filename in os.listdir('workingFolder'):
    #     if not debugMode:
    #         os.remove(os.path.join('workingFolder', filename))

    # Loop through payloads and submit to Azure
    for payload in payloadList:
        # Reset job_id from previous loops
        job_id = None
        
        # Send request to Azure
        job_id = azure_batch.submit_synthesis(payload)

        # Wait for job to finish
        if job_id is not None:
            status = "Running"
            resultDownloadLink = None
            
            while True: # Must use break to exit loop
                # Get status
                response = azure_batch.get_synthesis(job_id)
                status = response.json()['status'] # type: ignore
                if status == 'Succeeded':
                    print('Batch synthesis job succeeded')
                    resultDownloadLink = azure_batch.get_synthesis(job_id).json()['outputs']['result'] # type: ignore
                    break
                elif status == 'Failed':
                    print('ERROR: Batch synthesis job failed!')
                    print("Reason:" + response.reason) # type: ignore
                    break
                else:
                    print(f'Batch synthesis job is still running, status [{status}]')
                    time.sleep(5)
            
            # Download resultig zip file
            if resultDownloadLink is not None:
                # Download zip file
                urlResponse = urlopen(resultDownloadLink)

                # If debug mode, save zip file to disk
                # if debugMode:
                #     if secondPass == False:
                #         zipName = 'azureBatch.zip'
                #     else:
                #         zipName = 'azureBatchPass2.zip'

                #     zipPath = os.path.join('workingFolder', zipName)
                #     with open(zipPath, 'wb') as f:
                #         f.write(urlResponse.read())
                #     # Reset urlResponse so it can be read again
                #     urlResponse = urlopen(resultDownloadLink)

                # Process zip file    
                virtualResultZip = io.BytesIO(urlResponse.read())
                zipdata = zipfile.ZipFile(virtualResultZip)
                zipinfos = zipdata.infolist()

                # Reorder zipinfos so the file names are in alphanumeric order
                zipinfos.sort(key=lambda x: x.filename)

                # Only extract necessary files, and rename them while doing so
                for file in zipinfos:
                    if file.filename == "summary.json":
                        zipdata.extract(file, f"workingFolder/{langDict.get('translation_target_language')}") 
                        pass
                    elif "json" not in file.filename:
                        # Rename file to match first entry in remainingDownloadedEntriesDict, then extract
                        currentFileNum = remainingDownloadedEntriesList[0]
                        file.filename = str(currentFileNum) + '.mp3'
                        #file.filename = file.filename.lstrip('0')

                        # Add file path to subsDict then remove from remainingDownloadedEntriesList
                        subsDict[currentFileNum]['TTS_FilePath'] = os.path.join('workingFolder', f"{langDict.get('translation_target_language')}", str(currentFileNum)) + '.mp3'
                        # Extract file
                        zipdata.extract(file, f"workingFolder/{langDict.get('translation_target_language')}")
                        # Remove entry from remainingDownloadedEntriesList
                        remainingDownloadedEntriesList.pop(0)

    return subsDict

