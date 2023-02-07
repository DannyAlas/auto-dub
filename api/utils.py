import csv
from msilib import type_string
import re

def srt_to_dict(lines, addBufferMilliseconds) -> dict:
    """
    Takes a list of lines from an srt file and returns a dictionary

    Parameters
    ----------
    lines : list
        list of lines from an srt file
    addBufferMilliseconds : int
        number of milliseconds to add to the start and end of each srt line
    
    Returns
    -------
    dict
        with the following structure:
        {
        key: str
            the srt line Number
        value: dict
            {
                'start_ms': str 
                    start time in milliseconds, 
                'end_ms': str 
                    end time in milliseconds, 
                'duration_ms': str 
                    duration in milliseconds, 
                'text': str 
                    the text of the subtitle, 
                'break_until_next': int 
                    number of milliseconds until the next subtitle, 
                'srt_timestamps_line': str 
                    the srt formatted timestamps i.e. '00:00:03,400 --> 00:00:06,177',
                'start_ms_buffered': str
                    start time in milliseconds with buffer [if buffer = 0 this is the same as start_ms], 
                'end_ms_buffered': int
                    end time in milliseconds with buffer [if buffer = 0 this is the same as end_ms], 
                'duration_ms_buffered': str
                    duration of srt line in milliseconds with buffer [if buffer = 0 this is the same as duration_ms]
            }
        }    
    """
    # Matches the following example with regex:    00:00:20,130 --> 00:00:23,419
    subtitleTimeLineRegex = re.compile(r'\d\d:\d\d:\d\d,\d\d\d --> \d\d:\d\d:\d\d,\d\d\d')

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
                if (lineNum+count) < len(lines) and lines[lineNum + count].strip():
                    lineWithSubtitleText += ' ' + lines[lineNum + count].strip()
                    count += 1
                else:
                    break

            # Create empty dictionary with keys for start and end times and subtitle text
            subsDict[line] = {'start_ms': '', 'end_ms': '', 'duration_ms': '', 'text': '', 'break_until_next': '', 'srt_timestamps_line': lineWithTimestamps}

            time = lineWithTimestamps.split(' --> ')
            time1 = time[0].split(':')
            time2 = time[1].split(':')

            # Converts the time to milliseconds
            processedTime1 = int(time1[0]) * 3600000 + int(time1[1]) * 60000 + int(time1[2].split(',')[0]) * 1000 + int(time1[2].split(',')[1]) #/ 1000 #Uncomment to turn into seconds
            processedTime2 = int(time2[0]) * 3600000 + int(time2[1]) * 60000 + int(time2[2].split(',')[0]) * 1000 + int(time2[2].split(',')[1]) #/ 1000 #Uncomment to turn into seconds
            timeDifferenceMs = str(processedTime2 - processedTime1)

            # Adjust times with buffer
            if addBufferMilliseconds > 0:
                subsDict[line]['start_ms_buffered'] = str(processedTime1 + addBufferMilliseconds)
                subsDict[line]['end_ms_buffered'] = str(processedTime2 - addBufferMilliseconds)
                subsDict[line]['duration_ms_buffered'] = str((processedTime2 - addBufferMilliseconds) - (processedTime1 + addBufferMilliseconds))
            else:
                subsDict[line]['start_ms_buffered'] = str(processedTime1)
                subsDict[line]['end_ms_buffered'] = str(processedTime2)
                subsDict[line]['duration_ms_buffered'] = str(processedTime2 - processedTime1)
            
            # Set the keys in the dictionary to the values
            subsDict[line]['start_ms'] = str(processedTime1)
            subsDict[line]['end_ms'] = str(processedTime2)
            subsDict[line]['duration_ms'] = timeDifferenceMs
            subsDict[line]['text'] = lineWithSubtitleText
            if lineNum > 0:
                # Goes back to previous line's dictionary and writes difference in time to current line
                subsDict[str(int(line)-1)]['break_until_next'] = processedTime1 - int(subsDict[str(int(line) - 1)]['end_ms'])
            else:
                subsDict[line]['break_until_next'] = 0


    # Apply the buffer to the start and end times by setting copying over the buffer values to main values
    for key, value in subsDict.items():
        if addBufferMilliseconds > 0:
            subsDict[key]['start_ms'] = value['start_ms_buffered']
            subsDict[key]['end_ms'] = value['end_ms_buffered']
            subsDict[key]['duration_ms'] = value['duration_ms_buffered']
    
    return subsDict

def get_duration(filename) -> int:
    """
    Get the duration of a video file in milliseconds. Uses ffprobe.
    
    Parameters
    ----------
    filename : str
        The filename of the video file
    
    Returns
    -------
    durationMS : int
        The duration of the video file in milliseconds
    
    """
    import subprocess, json

    result = subprocess.check_output(
            f'ffprobe -v quiet -show_streams -select_streams v:0 -of json "{filename}"', shell=True).decode()
    fields = json.loads(result)['streams'][0]
    try:
        duration = fields['tags']['DURATION']
    except KeyError:
        duration = fields['duration']
    durationMS = round(float(duration)*1000) # Convert to milliseconds
    return durationMS

def parseBool(string):
    """
    Interprets a string as a boolean. Returns True or False

    Parameters
    ----------
    string : str
        The string to be interpreted as a boolean
    
    Returns
    -------
    bool
        True or False
    """
    if type(string) == str:
        if string.lower() == 'true':
            return True
        elif string.lower() == 'false':
            return False
    elif type(string) == bool:
        if string == True:
            return True
        elif string == False:
            return False
    else:
        raise ValueError('Not a valid boolean string')

def csv_to_dict(csvFilePath):
    """
    Returns a list of dictionaries from a csv file. Where the key is the column name and the value is the value in that column. The column names are set by the first row of the csv file

    Parameters
    ----------
    csvFilePath : str
        The path to the csv file
    """
    with open(csvFilePath, "r", encoding='utf-8-sig') as data:
        entriesDictsList = []
        for line in csv.DictReader(data):
            entriesDictsList.append(line)
    return entriesDictsList

def txt_to_list(txtFilePath):
    """
    Returns a list of strings from a txt file. Each line in the txt file is an entry in the list. Blank lines and lines starting with # are ignored.

    Parameters
    ----------
    txtFilePath : str
        The path to the txt file
    """
    with open(txtFilePath, "r", encoding='utf-8-sig') as data:
        entriesList = []
        for line in data:
            if line.strip() != '' and line.strip()[0] != '#':
                entriesList.append(line.strip())
    return entriesList
