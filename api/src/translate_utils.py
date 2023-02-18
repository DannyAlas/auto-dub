import copy
import html
import os
import re
from operator import itemgetter
from typing import Any

from utils import csv_to_dict, txt_to_list

# Import files from SSML_Customization folder
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

# ================================================================================================
#                           Helper Functions for translating text
# ================================================================================================


def create_sub_dict(srtFile, addBufferMilliseconds: int = 0):
    """Creates a dictionary of subtitles from an SRT file

    Args:
        srtFile (str): The path to the SRT file
        addBufferMilliseconds (int, optional): The number of milliseconds to add to the start and end times of the subtitles. Defaults to 0.

    Returns:
        dict: A dictionary of subtitles

    """
    with open(srtFile, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    # Matches the following example with regex:    00:00:20,130 --> 00:00:23,419
    subtitleTimeLineRegex = re.compile(
        r"\d\d:\d\d:\d\d,\d\d\d --> \d\d:\d\d:\d\d,\d\d\d"
    )

    # Create a dictionary
    subsDict = {}

    # Enumerate lines, and if a line in lines contains only an integer, put that number in the key, and a dictionary in the value
    # The dictionary contains the start, ending, and duration of the subtitles as well as the text
    # The next line uses the syntax HH:MM:SS,MMM --> HH:MM:SS,MMM . Get the difference between the two times and put that in the dictionary
    # For the line after that, put the text in the dictionary
    for lineNum, line in enumerate(lines):
        line = line.strip()
        if line.isdigit() and subtitleTimeLineRegex.match(lines[lineNum + 1]):
            lineWithTimestamps = lines[lineNum + 1].strip()
            lineWithSubtitleText = lines[lineNum + 2].strip()

            # If there are more lines after the subtitle text, add them to the text
            count = 3
            while True:
                # Check if the next line is blank or not
                if (lineNum + count) < len(lines) and lines[lineNum + count].strip():
                    lineWithSubtitleText += " " + lines[lineNum + count].strip()
                    count += 1
                else:
                    break

            # Create empty dictionary with keys for start and end times and subtitle text
            subsDict[line] = {
                "start_ms": "",
                "end_ms": "",
                "duration_ms": "",
                "text": "",
                "break_until_next": "",
                "srt_timestamps_line": lineWithTimestamps,
            }

            time = lineWithTimestamps.split(" --> ")
            time1 = time[0].split(":")
            time2 = time[1].split(":")

            # Converts the time to milliseconds
            processedTime1 = (
                int(time1[0]) * 3600000
                + int(time1[1]) * 60000
                + int(time1[2].split(",")[0]) * 1000
                + int(time1[2].split(",")[1])
            )  # / 1000 #Uncomment to turn into seconds
            processedTime2 = (
                int(time2[0]) * 3600000
                + int(time2[1]) * 60000
                + int(time2[2].split(",")[0]) * 1000
                + int(time2[2].split(",")[1])
            )  # / 1000 #Uncomment to turn into seconds
            timeDifferenceMs = str(processedTime2 - processedTime1)

            # Adjust times with buffer
            if addBufferMilliseconds > 0:
                subsDict[line]["start_ms_buffered"] = str(
                    processedTime1 + addBufferMilliseconds
                )
                subsDict[line]["end_ms_buffered"] = str(
                    processedTime2 - addBufferMilliseconds
                )
                subsDict[line]["duration_ms_buffered"] = str(
                    (processedTime2 - addBufferMilliseconds)
                    - (processedTime1 + addBufferMilliseconds)
                )
            else:
                subsDict[line]["start_ms_buffered"] = str(processedTime1)
                subsDict[line]["end_ms_buffered"] = str(processedTime2)
                subsDict[line]["duration_ms_buffered"] = str(
                    processedTime2 - processedTime1
                )

            # Set the keys in the dictionary to the values
            subsDict[line]["start_ms"] = str(processedTime1)
            subsDict[line]["end_ms"] = str(processedTime2)
            subsDict[line]["duration_ms"] = timeDifferenceMs
            subsDict[line]["text"] = lineWithSubtitleText
            if lineNum > 0:
                # Goes back to previous line's dictionary and writes difference in time to current line
                subsDict[str(int(line) - 1)]["break_until_next"] = processedTime1 - int(
                    subsDict[str(int(line) - 1)]["end_ms"]
                )
            else:
                subsDict[line]["break_until_next"] = 0

    # Apply the buffer to the start and end times by setting copying over the buffer values to main values
    for key, value in subsDict.items():
        if addBufferMilliseconds > 0:
            subsDict[key]["start_ms"] = value["start_ms_buffered"]
            subsDict[key]["end_ms"] = value["end_ms_buffered"]
            subsDict[key]["duration_ms"] = value["duration_ms_buffered"]

    return subsDict


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
        findWordRegex = rf'(\b["\'()]?{word}[.,!?()]?["\']?\b)'  # Find the word, with optional punctuation after, and optional quotes before or after
        text = re.sub(
            findWordRegex,
            r'<span class="notranslate">\1</span>',
            text,
            flags=re.IGNORECASE,
        )
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

    text = text.replace('<span class="notranslate">', "").replace("</span>", "")
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
        if manualTranslatedText["Language Code"] == langcode:
            originalText = manualTranslatedText["Original Text"]
            findWordRegex = rf'(\b["\'()]?{originalText}[.,!?()]?["\']?\b)'
            text = re.sub(
                findWordRegex,
                r'<span class="notranslate">\1</span>',
                text,
                flags=re.IGNORECASE,
            )
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
        if manualTranslatedText["Language Code"] == langcode:
            originalText = manualTranslatedText["Original Text"]
            translatedText = manualTranslatedText["Translated Text"]
            findWordRegex = rf'(\b["\'()]?{originalText}[.,!?()]?["\']?\b)'
            text = re.sub(findWordRegex, translatedText, text, flags=re.IGNORECASE)
    return text


def combine_subtitles_advanced(inputDict, maxCharacters=200):
    """Combines subtitle lines that are close together and have a similar speaking rate. Useful when sentences are split into multiple subtitle lines. Voice synthesis will have fewer unnatural pauses.

    TODO: REWRITE THIS FUNCTION AT SOME POINT, split into multiple functions with more options
    """
    charRateGoal = 20  # 20
    gapThreshold = 100  # The maximum gap between subtitles to combine
    noMorePossibleCombines = False
    # Convert dictionary to list of dictionaries of the values
    entryList = []

    for key, value in inputDict.items():
        value["originalIndex"] = int(key) - 1
        entryList.append(value)

    while not noMorePossibleCombines:
        entryList, noMorePossibleCombines = combine_single_pass(
            entryList, charRateGoal, gapThreshold, maxCharacters
        )

    # Convert the list back to a dictionary then return it
    return dict(enumerate(entryList, start=1))


def calc_dict_speaking_rates(inputDict, dictKey="translated_text"):
    tempDict = copy.deepcopy(inputDict)
    for key, value in tempDict.items():
        tempDict[key]["char_rate"] = round(
            len(value[dictKey]) / (int(value["duration_ms"]) / 1000), 2
        )
    return tempDict


def calc_list_speaking_rates(inputList, charRateGoal, dictKey="translated_text"):
    tempList = copy.deepcopy(inputList)
    for i in range(len(tempList)):
        # Calculate the number of characters per second based on the duration of the entry
        tempList[i]["char_rate"] = round(
            len(tempList[i][dictKey]) / (int(tempList[i]["duration_ms"]) / 1000), 2
        )
        # Calculate the difference between the current char_rate and the goal char_rate - Absolute Value
        tempList[i]["char_rate_diff"] = abs(
            round(tempList[i]["char_rate"] - charRateGoal, 2)
        )
    return tempList


def combine_single_pass(entryListLocal, charRateGoal, gapThreshold, maxCharacters):
    """ """
    # Want to restart the loop if a change is made, so use this variable, otherwise break only if the end is reached
    reachedEndOfList = False
    noMorePossibleCombines = True  # Will be set to False if a combination is made

    # Use while loop because the list is being modified
    while not reachedEndOfList:

        # Need to update original index in here
        for entry in entryListLocal:
            entry["originalIndex"] = entryListLocal.index(entry)

        # Will use later to check if an entry is the last one in the list, because the last entry will have originalIndex equal to the length of the list - 1
        originalNumberOfEntries = len(entryListLocal)

        # Need to calculate the char_rate for each entry, any time something changes, so put it at the top of this loop
        entryListLocal = calc_list_speaking_rates(entryListLocal, charRateGoal)

        # Sort the list by the difference in speaking speed from charRateGoal
        priorityOrderedList = sorted(
            entryListLocal, key=itemgetter("char_rate_diff"), reverse=True
        )

        # Iterates through the list in order of priority, and uses that index to operate on entryListLocal
        # For loop is broken after a combination is made, so that the list can be re-sorted and re-iterated
        for progress, data in enumerate(priorityOrderedList):
            i = data["originalIndex"]
            # Check if last entry, and therefore will end loop when done with this iteration
            if progress == len(priorityOrderedList) - 1:
                reachedEndOfList = True

            # Check if the current entry is outside the upper and lower bounds
            if data["char_rate"] > charRateGoal or data["char_rate"] < charRateGoal:

                # Check if the entry is the first in entryListLocal, if so do not consider the previous entry
                if data["originalIndex"] == 0:
                    considerPrev = False
                else:
                    considerPrev = True

                # Check if the entry is the last in entryListLocal, if so do not consider the next entry
                if data["originalIndex"] == originalNumberOfEntries - 1:
                    considerNext = False
                else:
                    considerNext = True

                # Check if current entry is still in the list - if it has been combined with another entry, it will not be

                # Get the char_rate of the next and previous entries, if they exist, and calculate the difference
                # If the diff is positive, then it is lower than the current char_rate
                try:
                    nextCharRate = entryListLocal[i + 1]["char_rate"]
                    nextDiff = data["char_rate"] - nextCharRate
                except IndexError:
                    considerNext = False
                    nextCharRate = None
                    nextDiff = None
                try:
                    prevCharRate = entryListLocal[i - 1]["char_rate"]
                    prevDiff = data["char_rate"] - prevCharRate
                except IndexError:
                    considerPrev = False
                    prevCharRate = None
                    prevDiff = None

            else:
                continue

            # Define functions for combining with previous or next entries - Generated with copilot, it's possible this isn't perfect
            def combine_with_next():
                entryListLocal[i]["text"] = (
                    entryListLocal[i]["text"] + " " + entryListLocal[i + 1]["text"]
                )
                entryListLocal[i]["translated_text"] = (
                    entryListLocal[i]["translated_text"]
                    + " "
                    + entryListLocal[i + 1]["translated_text"]
                )
                entryListLocal[i]["end_ms"] = entryListLocal[i + 1]["end_ms"]
                entryListLocal[i]["end_ms_buffered"] = entryListLocal[i + 1][
                    "end_ms_buffered"
                ]
                entryListLocal[i]["duration_ms"] = int(
                    entryListLocal[i + 1]["end_ms"]
                ) - int(entryListLocal[i]["start_ms"])
                entryListLocal[i]["duration_ms_buffered"] = int(
                    entryListLocal[i + 1]["end_ms_buffered"]
                ) - int(entryListLocal[i]["start_ms_buffered"])
                entryListLocal[i]["srt_timestamps_line"] = (
                    entryListLocal[i]["srt_timestamps_line"].split(" --> ")[0]
                    + " --> "
                    + entryListLocal[i + 1]["srt_timestamps_line"].split(" --> ")[1]
                )
                del entryListLocal[i + 1]

            def combine_with_prev():
                entryListLocal[i - 1]["text"] = (
                    entryListLocal[i - 1]["text"] + " " + entryListLocal[i]["text"]
                )
                entryListLocal[i - 1]["translated_text"] = (
                    entryListLocal[i - 1]["translated_text"]
                    + " "
                    + entryListLocal[i]["translated_text"]
                )
                entryListLocal[i - 1]["end_ms"] = entryListLocal[i]["end_ms"]
                entryListLocal[i - 1]["end_ms_buffered"] = entryListLocal[i][
                    "end_ms_buffered"
                ]
                entryListLocal[i - 1]["duration_ms"] = int(
                    entryListLocal[i]["end_ms"]
                ) - int(entryListLocal[i - 1]["start_ms"])
                entryListLocal[i - 1]["duration_ms_buffered"] = int(
                    entryListLocal[i]["end_ms_buffered"]
                ) - int(entryListLocal[i - 1]["start_ms_buffered"])
                entryListLocal[i - 1]["srt_timestamps_line"] = (
                    entryListLocal[i - 1]["srt_timestamps_line"].split(" --> ")[0]
                    + " --> "
                    + entryListLocal[i]["srt_timestamps_line"].split(" --> ")[1]
                )
                del entryListLocal[i]

            # Choose whether to consider next and previous entries, and if neither then continue to next loop
            if data["char_rate"] > charRateGoal:
                # Check to ensure next/previous rates are lower than current rate, and the combined entry is not too long, and the gap between entries is not too large
                # Need to add check for considerNext and considerPrev first, because if run other checks when there is no next/prev value to check, it will throw an error
                if considerNext == False or nextDiff or nextDiff < 0 or (entryListLocal[i]["break_until_next"] >= gapThreshold) or (len(entryListLocal[i]["translated_text"]) + len(entryListLocal[i + 1]["translated_text"]) > maxCharacters):  # type: ignore
                    considerNext = False
                try:
                    if (
                        considerPrev == False
                        or not prevDiff
                        or prevDiff < 0
                        or (entryListLocal[i - 1]["break_until_next"] >= gapThreshold)
                        or (
                            len(entryListLocal[i - 1]["translated_text"])
                            + len(entryListLocal[i]["translated_text"])
                            > maxCharacters
                        )
                    ):
                        considerPrev = False
                except TypeError:
                    considerPrev = False

            elif data["char_rate"] < charRateGoal:
                # Check to ensure next/previous rates are higher than current rate
                if (
                    considerNext == False
                    or not nextDiff
                    or nextDiff > 0
                    or (entryListLocal[i]["break_until_next"] >= gapThreshold)
                    or (
                        len(entryListLocal[i]["translated_text"])
                        + len(entryListLocal[i + 1]["translated_text"])
                        > maxCharacters
                    )
                ):
                    considerNext = False
                try:
                    if (
                        considerPrev == False
                        or not prevDiff
                        or prevDiff > 0
                        or (entryListLocal[i - 1]["break_until_next"] >= gapThreshold)
                        or (
                            len(entryListLocal[i - 1]["translated_text"])
                            + len(entryListLocal[i]["translated_text"])
                            > maxCharacters
                        )
                    ):
                        considerPrev = False
                except TypeError:
                    considerPrev = False
            else:
                continue

            # Continue to next loop if neither are considered
            if not considerNext and not considerPrev:
                continue

            # Should only reach this point if two entries are to be combined
            if data["char_rate"] > charRateGoal:
                # If both are to be considered, then choose the one with the lower char_rate
                if considerNext and considerPrev and nextDiff:
                    if nextDiff < prevDiff:
                        combine_with_next()
                        noMorePossibleCombines = False
                        break
                    else:
                        combine_with_prev()
                        noMorePossibleCombines = False
                        break
                # If only one is to be considered, then combine with that one
                elif considerNext:
                    combine_with_next()
                    noMorePossibleCombines = False
                    break
                elif considerPrev:
                    combine_with_prev()
                    noMorePossibleCombines = False
                    break
                else:
                    print(f"Error U: Should not reach this point! Current entry = {i}")
                    print(f"Current Entry Text = {data['text']}")
                    continue

            elif data["char_rate"] < charRateGoal:
                # If both are to be considered, then choose the one with the higher char_rate
                if considerNext and considerPrev and nextDiff:
                    if nextDiff > prevDiff:
                        combine_with_next()
                        noMorePossibleCombines = False
                        break
                    else:
                        combine_with_prev()
                        noMorePossibleCombines = False
                        break
                # If only one is to be considered, then combine with that one
                elif considerNext:
                    combine_with_next()
                    noMorePossibleCombines = False
                    break
                elif considerPrev:
                    combine_with_prev()
                    noMorePossibleCombines = False
                    break
                else:
                    print(f"Error L: Should not reach this point! Index = {i}")
                    print(f"Current Entry Text = {data['text']}")
                    continue
    return entryListLocal, noMorePossibleCombines


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
