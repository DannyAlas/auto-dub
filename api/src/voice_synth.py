import copy
import datetime
import io
import json
import os
import re
import time
import zipfile
from typing import Any
from pydub import AudioSegment
from pydub.silence import detect_leading_silence
from typing import Literal, Union
from urllib.request import urlopen

import azure_batch
from utils import csv_to_dict, parseBool, txt_to_list

interpretAsOverrideFile = os.path.abspath("SSML_Customization/interpret-as.csv")
interpretAsEntries = csv_to_dict(interpretAsOverrideFile)
urlListFile = os.path.abspath("SSML_Customization/url_list.txt")
urlList = txt_to_list(urlListFile)
aliasOverrideFile = os.path.abspath("SSML_Customization/aliases.csv")
aliasEntries = csv_to_dict(aliasOverrideFile)
phonemeFile = os.path.abspath("SSML_Customization/Phoneme_Pronunciation.csv")
phonemeEntries = csv_to_dict(phonemeFile)


def add_interpretas_tags(text):
    # Add interpret-as tags from interpret-as.csv
    for entryDict in interpretAsEntries:
        # Get entry info
        entryText = entryDict["Text"]
        entryInterpretAsType = entryDict["interpret-as Type"]
        isCaseSensitive = parseBool(entryDict["Case Sensitive (True/False)"])
        entryFormat = entryDict["Format (Optional)"]

        # Create say-as tag
        if entryFormat == "":
            sayAsTagStart = rf'<say-as interpret-as="{entryInterpretAsType}">'
        else:
            sayAsTagStart = rf'<say-as interpret-as="{entryInterpretAsType}" format="{entryFormat}">'

        # Find and replace the word
        findWordRegex = rf'(\b["\']?{entryText}[.,!?]?["\']?\b)'  # Find the word, with optional punctuation after, and optional quotes before or after
        if isCaseSensitive:
            text = re.sub(
                findWordRegex, rf"{sayAsTagStart}\1</say-as>", text
            )  # Uses group reference, so remember regex must be in parentheses

        else:
            text = re.sub(
                findWordRegex, rf"{sayAsTagStart}\1</say-as>", text, flags=re.IGNORECASE
            )

    # Add interpret-as tags from url_list.txt
    for url in urlList:
        # This regex expression will match the top level domain extension, and the punctuation before/after it, and any periods, slashes or colons
        # It will then put the say-as characters tag around all matches
        punctuationRegex = re.compile(r"((?:\.[a-z]{2,6}(?:\/|$|\s))|(?:[\.\/:]+))")
        taggedURL = re.sub(
            punctuationRegex, r'<say-as interpret-as="characters">\1</say-as>', url
        )
        # Replace any instances of the URL with the tagged version
        text = text.replace(url, taggedURL)

    return text


def add_alias_tags(text):
    for entryDict in aliasEntries:
        # Get entry info
        entryText = entryDict["Original Text"]
        entryAlias = entryDict["Alias"]
        if entryDict["Case Sensitive (True/False)"] == "":
            isCaseSensitive = False
        else:
            isCaseSensitive = parseBool(entryDict["Case Sensitive (True/False)"])

        # Find and replace the word
        findWordRegex = rf'\b["\'()]?{entryText}[.,!?()]?["\']?\b'  # Find the word, with optional punctuation after, and optional quotes before or after
        if isCaseSensitive:
            text = re.sub(findWordRegex, rf"{entryAlias}", text)
        else:
            text = re.sub(findWordRegex, rf"{entryAlias}", text, flags=re.IGNORECASE)
    return text


# Uses the phoneme pronunciation file to add phoneme tags to the text
def add_phoneme_tags(text):
    for entryDict in phonemeEntries:
        # Get entry info
        entryText = entryDict["Text"]
        entryPhoneme = entryDict["Phonetic Pronunciation"]
        entryAlphabet = entryDict["Phonetic Alphabet"]

        if entryDict["Case Sensitive (True/False)"] == "":
            isCaseSensitive = False
        else:
            isCaseSensitive = parseBool(entryDict["Case Sensitive (True/False)"])

        # Find and replace the word
        findWordRegex = rf'(\b["\'()]?{entryText}[.,!?()]?["\']?\b)'  # Find the word, with optional punctuation after, and optional quotes before or after
        if isCaseSensitive:
            text = re.sub(
                findWordRegex,
                rf'<phoneme alphabet="ipa" ph="{entryPhoneme}">\1</phoneme>',
                text,
            )
        else:
            text = re.sub(
                findWordRegex,
                rf'<phoneme alphabet="{entryAlphabet}" ph="{entryPhoneme}">\1</phoneme>',
                text,
                flags=re.IGNORECASE,
            )
    return text


def add_all_pronunciation_overrides(text):
    text = add_interpretas_tags(text)
    text = add_alias_tags(text)
    text = add_phoneme_tags(text)
    return text


def format_percentage_change(speedFactor):
    # Determine speedFactor value for Azure TTS. It should be either 'default' or a relative change.
    if speedFactor == 1.0:
        rate = "default"
    else:
        # Whether to add a plus sign to the number to relative change. A negative will automatically be added
        if speedFactor >= 1.0:
            percentSign = "+"
        else:
            percentSign = ""
        # Convert speedFactor float value to a relative percentage
        rate = percentSign + str(round((speedFactor - 1.0) * 100, 5)) + "%"
    return rate

def trim_clip(inputSound):
    trim_leading_silence: AudioSegment = lambda x: x[detect_leading_silence(x) :]   #type: ignore
    trim_trailing_silence: AudioSegment = lambda x: trim_leading_silence(x.reverse()).reverse() #type: ignore
    strip_silence: AudioSegment = lambda x: trim_trailing_silence(trim_leading_silence(x))  #type: ignore
    strippedSound = strip_silence(inputSound)   #type: ignore
    return strippedSound

def create_canvas(canvasDuration, frame_rate):
    canvas = AudioSegment.silent(duration=canvasDuration, frame_rate=frame_rate)
    return canvas

def insert_audio(canvas, audioToOverlay, startTimeMs):
    # Create a copy of the canvas
    canvasCopy = canvas
    # Overlay the audio onto the copy
    canvasCopy = canvasCopy.overlay(audioToOverlay, position=int(startTimeMs))
    # Return the copy
    return canvasCopy

def build_audio(subs_dict: dict, lang_dict, total_audio_length, two_pass_voice_synth=False, native_sample_rate=44100, skipSynthesize=False):
    """Builds the final audio file from the subs_dict and the audio files in the temp folder
    !!!!!!!!!!!!!!!!!!!!!!!!!!
    BROKEN - NEEDS TO BE FIXED
    !!!!!!!!!!!!!!!!!!!!!!!!!!
    """
    virtual_trimmed_file_dict = {}
    # First trim silence off the audio files
    for key, value in subs_dict.items():

        # Trim the clip and re-write file
        raw_clip = AudioSegment.from_file(value['TTS_FilePath'], format="mp3", frame_rate=native_sample_rate)
        trimmed_clip = trim_clip(raw_clip)

        # Create virtual file in dictionary with audio to be read later
        temp_trimmed_file = io.BytesIO()
        trimmed_clip.export(temp_trimmed_file, format="wav")
        virtual_trimmed_file_dict[key] = temp_trimmed_file
        key_index = list(subs_dict.keys()).index(key)
        print(f" Trimmed Audio: {key_index+1} of {len(subs_dict)}", end="\r")

    if two_pass_voice_synth == True:
        _ , subs_dict = synthesize_text_azure_batch(subs_dict, lang_dict, second_pass=True)
            
        for key, value in subs_dict.items():
            # Trim the clip and re-write file
            raw_clip = AudioSegment.from_file(value['TTS_FilePath'], format="mp3", frame_rate=native_sample_rate)
            trimmed_clip = trim_clip(raw_clip)

            trimmed_clip.export(virtual_trimmed_file_dict[key], format="wav")
            key_index = list(subs_dict.keys()).index(key)
            print(f" Trimmed Audio (2nd Pass): {key_index+1} of {len(subs_dict)}", end="\r")
        # Create canvas to overlay audio onto
    
    canvas = create_canvas(total_audio_length, native_sample_rate)

    # Stretch audio and insert into canvas
    for key, value in subs_dict.items():
        stretched_clip = AudioSegment.from_file(virtual_trimmed_file_dict[key], format="wav")
        virtual_trimmed_file_dict[key].seek(0) # Not 100% sure if this is necessary but it was in the other place it is used

        canvas = insert_audio(canvas, stretched_clip, value['start_ms'])
        key_index = list(subs_dict.keys()).index(key)
        print(f" Final Audio Processed: {key_index+1} of {len(subs_dict)}", end="\r")
    print("\n")

    canvas = canvas.set_channels(2) # Change from mono to stereo

    print("\nExporting audio file...")
    canvas.export('outputFileName', format="mp3", bitrate="192k")

    return subs_dict

def synthesize_text_azure_batch(
    subs_dict: dict,
    lang_dict,
    second_pass=False,
    azure_sentence_pause: Union[Literal["default"], int] = "default",
) -> Any:
    """
    Synthesize text using Azure TTS. This function will send a batch of text to Azure TTS, and return a dict of the audio files and summary file.
    
    Returns
    -------
    dict
        A dict containing the audio files and summary file.
        {
            'file name': bytes,
        }
    """
    # Write speed factor to subs_dict in correct format
    for key, value in subs_dict.items():
        if second_pass:
            subs_dict[key]["speed_factor"] = format_percentage_change(
                subs_dict[key]["speed_factor"]
            )
        else:
            # subs_dict[key]['speed_factor'] = float(1.0)
            subs_dict[key]["speed_factor"] = "default"

    def create_request_payload(remainingEntriesDict):
        # Create SSML for all subtitles
        ssmlJson = []
        payloadSizeInBytes = 0
        tempDict = dict(
            remainingEntriesDict
        )  # Need to do this to avoid changing the original dict which would mess with the loop

        for key, value in tempDict.items():
            rate = tempDict[key]["speed_factor"]
            text = tempDict[key]["translated_text"]
            language = lang_dict["synth_language_code"]
            voice = lang_dict["synth_voice_name"]

            # Create strings for prosody tags. Only add them if rate is not default, because azure charges for characters of optional tags
            if rate == "default":
                pOpenTag = ""
                pCloseTag = ""
            else:
                pOpenTag = f"<prosody rate='{rate}'>"
                pCloseTag = "</prosody>"

            # Create string for sentence pauses, if not default
            if not azure_sentence_pause == "default" and type(azure_sentence_pause) == int:
                pauseTag = f'<mstts:silence type="Sentenceboundary-exact" value="{azure_sentence_pause}ms"/>'
            else:
                pauseTag = ""

            # Process text using pronunciation customization set by user
            text = add_all_pronunciation_overrides(text)

            # Create the SSML for each subtitle
            ssml = (
                f"<speak version='1.0' xml:lang='{language}' xmlns='http://www.w3.org/2001/10/synthesis' "
                "xmlns:mstts='http://www.w3.org/2001/mstts'>"
                f"<voice name='{voice}'>{pauseTag}"
                f"{pOpenTag}{text}{pCloseTag}</voice></speak>"
            )
            ssmlJson.append({"text": ssml})

            # Construct request payload with SSML
            # Reconstruct payload with every loop with new SSML so that the payload size is accurate
            now = datetime.datetime.now()
            pendingPayload = {
                "displayName": lang_dict["synth_language_code"]
                + "-"
                + now.strftime("%Y-%m-%d %H:%M:%S"),
                "description": "Batch synthesis of "
                + lang_dict["synth_language_code"]
                + " subtitles",
                "textType": "SSML",
                # To use custom voice, see original example code script linked from azure_batch.py
                "inputs": ssmlJson,
                "properties": {
                    "outputFormat": "audio-48khz-192kbitrate-mono-mp3",
                    "wordBoundaryEnabled": False,
                    "sentenceBoundaryEnabled": False,
                    "concatenateResult": False,
                    "decompressOutputFiles": False,
                },
            }
            # Azure TTS Batch requests require payload must be under 500 kilobytes, so check payload is under 500,000 bytes. Not sure if they actually mean kibibytes, assume worst case.
            # Payload will be formatted as json so must account for that too by doing json.dumps(), otherwise calculated size will be inaccurate
            payloadSizeInBytes = len(str(json.dumps(pendingPayload)).encode("utf-8"))

            if (
                payloadSizeInBytes > 495000 or len(ssmlJson) > 995
            ):  # Leave some room for anything unexpected. Also number of inputs must be below 1000
                # If payload would be too large, ignore the last entry and break out of loop
                return payload, remainingEntriesDict  # type: ignore
            else:
                payload = copy.deepcopy(
                    pendingPayload
                )  # Must make deepycopy otherwise ssmlJson will be updated in both instead of just pendingPayload
                # Remove entry from remainingEntriesDict if it was added to payload
                remainingEntriesDict.pop(key)

        # If all the rest of the entries fit, return the payload
        return payload, remainingEntriesDict  # type: ignore

    # ------------------------- End create_request_payload() -----------------------------------

    # Create payloads, split into multiple if necessary
    payloadList = []
    remainingPayloadEntriesDict = dict(
        subs_dict
    )  # Will remove entries as they are added to payloads
    while len(remainingPayloadEntriesDict) > 0:
        payloadToAppend, remainingPayloadEntriesDict = create_request_payload(
            remainingPayloadEntriesDict
        )
        payloadList.append(payloadToAppend)

    # Tell user if request will be broken up into multiple payloads
    if len(payloadList) > 1:
        print(
            f"Payload will be broken up into {len(payloadList)} requests (due to Azure size limitations)."
        )

    # Use to keep track of filenames downloaded via separate zip files. WIll remove as they are downloaded
    remainingDownloadedEntriesList = list(subs_dict.keys())

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

            while True:  # Must use break to exit loop
                # Get status
                response = azure_batch.get_synthesis(job_id)
                status = response.json()["status"]  # type: ignore
                if status == "Succeeded":
                    print("Batch synthesis job succeeded")
                    resultDownloadLink = azure_batch.get_synthesis(job_id).json()["outputs"]["result"]  # type: ignore
                    break
                elif status == "Failed":
                    print("ERROR: Batch synthesis job failed!")
                    print("Reason:" + response.reason)  # type: ignore
                    break
                else:
                    print(f"Batch synthesis job is still running, status [{status}]")
                    time.sleep(5)

            # Download resultig zip file
            if resultDownloadLink is not None:
                # Download zip file
                # urlResponse = urlopen(resultDownloadLink)
                import requests, zipfile, io
                r = requests.get(resultDownloadLink)

                # os.mkdir("workingFolder")

                # Process zip file

                zipdata = zipfile.ZipFile(io.BytesIO(r.content))
                zipinfos = zipdata.infolist()

                # Reorder zipinfos so the file names are in alphanumeric order
                zipinfos.sort(key=lambda x: x.filename)

                # Only extract necessary files, and rename them while doing so
                upload_files = {}
                for file in zipinfos:
                    if file.filename == "summary.json":
                        upload_files[file.filename] = zipdata.read(file)
                        pass
                    elif "json" not in file.filename:
                        # Rename file to match first entry in remainingDownloadedEntriesDict, then extract
                        currentFileNum = remainingDownloadedEntriesList[0]
                        file.filename = str(currentFileNum) + ".mp3"
                        # file.filename = file.filename.lstrip('0')

                        # Extract file
                        upload_files[file.filename] = zipdata.read(file)

                        # Remove entry from remainingDownloadedEntriesList
                        remainingDownloadedEntriesList.pop(0)

                return upload_files, subs_dict
